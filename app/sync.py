"""Livraison vérifiée vers le Kindle (serveur SSH de KOReader, shell busybox).

Pas de SFTP (absent de dropbear sur le Kindle) : les fichiers sont envoyés par
`cat > fichier.tmp && mv`, puis vérifiés par empreinte relue sur le Kindle.
"""
from __future__ import annotations

import json
import logging
import os
import shlex
import socket
from pathlib import Path

import paramiko
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from . import status
from .config import STATE, Config
from .generate import SORTIE, sha_fichier

log = logging.getLogger("kit.sync")
CLE = STATE / "id_ed25519"
KNOWN_HOSTS = STATE / "known_hosts"
EXTENSIONS_LIVRES = (".epub", ".pdf")


def assurer_cle() -> str:
    """Crée la clé SSH dédiée au premier démarrage et renvoie la clé publique."""
    pub = Path(str(CLE) + ".pub")
    if not CLE.exists():
        CLE.parent.mkdir(parents=True, exist_ok=True)
        cle = ed25519.Ed25519PrivateKey.generate()
        prive = cle.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH,
            serialization.NoEncryption(),
        )
        fd = os.open(CLE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(prive)
        publique = cle.public_key().public_bytes(
            serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH,
        ).decode()
        pub.write_text(f"{publique} kit-urgence@nas\n", encoding="utf-8")
    return pub.read_text(encoding="utf-8").strip()


def port_ouvert(cfg: Config, delai: float = 2.0) -> bool:
    if not cfg.kindle.host:
        return False  # IP du Kindle non renseignée dans config.yaml
    try:
        with socket.create_connection((cfg.kindle.host, cfg.kindle.port), timeout=delai):
            return True
    except OSError:
        return False


class _PremiereConnexion(paramiko.MissingHostKeyPolicy):
    """Accepte la clé d'hôte du Kindle à la première connexion, puis l'épingle."""

    def missing_host_key(self, client, hostname, key):
        client.get_host_keys().add(hostname, key.get_name(), key)
        KNOWN_HOSTS.parent.mkdir(parents=True, exist_ok=True)
        client.save_host_keys(str(KNOWN_HOSTS))
        log.warning("Clé d'hôte du Kindle enregistrée (première connexion) : %s",
                    key.get_fingerprint().hex())


def _connexion(cfg: Config) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    if KNOWN_HOSTS.exists():
        client.load_host_keys(str(KNOWN_HOSTS))
    client.set_missing_host_key_policy(_PremiereConnexion())
    hote = cfg.kindle.host if cfg.kindle.port == 22 else f"[{cfg.kindle.host}]:{cfg.kindle.port}"
    client.connect(
        cfg.kindle.host, port=cfg.kindle.port, username=cfg.kindle.user,
        key_filename=str(CLE), look_for_keys=False, allow_agent=False, timeout=10,
    )
    log.debug("Connecté à %s", hote)
    return client


def _exec(client: paramiko.SSHClient, cmd: str, donnees: Path | None = None) -> tuple[int, str]:
    transport = client.get_transport()
    chan = transport.open_session()
    chan.exec_command(cmd)
    if donnees is not None:
        with donnees.open("rb") as f:
            for bloc in iter(lambda: f.read(64 * 1024), b""):
                chan.sendall(bloc)
    chan.shutdown_write()
    sortie = b""
    while True:
        morceau = chan.recv(65536)
        if not morceau:
            break
        sortie += morceau
    code = chan.recv_exit_status()
    chan.close()
    return code, sortie.decode("utf-8", errors="replace")


def _empreinte_distante(client, chemin: str) -> str | None:
    code, out = _exec(client, f"sha256sum {shlex.quote(chemin)} 2>/dev/null")
    if code == 0 and out.strip():
        return out.split()[0]
    return None


def _empreintes_distantes(client, dest: str) -> dict | None:
    """{nom: sha256} des livres présents, ou None si sha256sum est indisponible."""
    code, out = _exec(client, "command -v sha256sum >/dev/null 2>&1 && echo oui")
    if out.strip() != "oui":
        return None
    code, out = _exec(
        client, f"cd {shlex.quote(dest)} && for f in *; do [ -f \"$f\" ] && sha256sum \"$f\"; done")
    empreintes = {}
    for ligne in out.splitlines():
        sha, _, nom = ligne.partition("  ")
        if len(sha) == 64 and nom:
            empreintes[nom] = sha
    return empreintes


def _tailles_distantes(client, dest: str) -> dict:
    """{nom: taille en octets} des fichiers présents sur le Kindle."""
    code, out = _exec(
        client,
        f"cd {shlex.quote(dest)} && for f in *; do [ -f \"$f\" ] && "
        "printf '%s\\t%s\\n' \"$(wc -c < \"$f\")\" \"$f\"; done")
    tailles = {}
    for ligne in out.splitlines():
        taille, _, nom = ligne.partition("\t")
        if taille.strip().isdigit() and nom:
            tailles[nom] = int(taille.strip())
    return tailles


def livrer(cfg: Config) -> dict:
    """Envoie les livres modifiés, supprime les obsolètes et vérifie le résultat."""
    manifest_local = json.loads((SORTIE / "manifest.json").read_text(encoding="utf-8"))
    dest = cfg.kindle.dossier.rstrip("/")
    client = _connexion(cfg)
    try:
        code, _ = _exec(client, f"mkdir -p {shlex.quote(dest)}")
        if code != 0:
            raise RuntimeError(f"Impossible de créer {dest} sur le Kindle")

        # Empreintes réelles des fichiers présents sur le Kindle (sha256sum de busybox) ;
        # à défaut, on se fie au manifest déposé lors de la dernière livraison.
        distant = _empreintes_distantes(client, dest)
        if distant is None:
            code, brut = _exec(client, f"cat {shlex.quote(dest + '/manifest.json')} 2>/dev/null")
            try:
                annonce = json.loads(brut).get("livres", {}) if code == 0 and brut.strip() else {}
            except json.JSONDecodeError:
                annonce = {}
            # Le manifest ne suffit pas : on ne garde que les fichiers de la bonne taille
            tailles = _tailles_distantes(client, dest)
            distant = {
                nom: sha for nom, sha in annonce.items()
                if (SORTIE / nom).exists() and tailles.get(nom) == (SORTIE / nom).stat().st_size
            }

        envoyes = []
        for nom, sha in manifest_local["livres"].items():
            if distant.get(nom) == sha:
                continue
            tmp = f"{dest}/.{nom}.tmp"
            cible = f"{dest}/{nom}"
            code, out = _exec(
                client,
                f"cat > {shlex.quote(tmp)} && mv -f {shlex.quote(tmp)} {shlex.quote(cible)}",
                SORTIE / nom,
            )
            if code != 0:
                raise RuntimeError(f"Échec de l'envoi de {nom} : {out.strip()}")
            envoyes.append(nom)

        # Suppression des livres obsolètes (uniquement .epub/.pdf et .tmp du dossier Urgence)
        code, liste = _exec(client, f"ls -1A {shlex.quote(dest)}")
        for nom in liste.splitlines():
            obsolete = nom.endswith(EXTENSIONS_LIVRES) and nom not in manifest_local["livres"]
            if obsolete or nom.endswith(".tmp"):
                _exec(client, f"rm -f {shlex.quote(dest + '/' + nom)}")

        # Vérification : empreinte de chaque livre relue sur le Kindle
        methode = "sha256"
        for nom, sha in manifest_local["livres"].items():
            reel = _empreinte_distante(client, f"{dest}/{nom}")
            if reel is None:
                methode = "taille"
                code, out = _exec(client, f"wc -c < {shlex.quote(dest + '/' + nom)}")
                attendu = (SORTIE / nom).stat().st_size
                if code != 0 or out.strip() != str(attendu):
                    raise RuntimeError(f"Vérification échouée pour {nom} (taille)")
            elif reel != sha:
                raise RuntimeError(f"Vérification échouée pour {nom} (empreinte différente)")

        # Le manifest est écrit en dernier : il ne décrit que ce qui est vérifié
        tmp_m = f"{dest}/.manifest.json.tmp"
        code, out = _exec(
            client,
            f"cat > {shlex.quote(tmp_m)} && mv -f {shlex.quote(tmp_m)} "
            f"{shlex.quote(dest + '/manifest.json')}",
            SORTIE / "manifest.json",
        )
        if code != 0:
            raise RuntimeError(f"Échec de l'écriture du manifest : {out.strip()}")
    finally:
        client.close()

    log.info("Livraison vérifiée (%s) : %d livre(s) envoyé(s)", methode, len(envoyes))
    return status.update(
        version_kindle=manifest_local["version"],
        derniere_livraison=status.now(),
        derniere_erreur=None,
        derniere_verification=methode,
        derniers_envoyes=envoyes,
    )


def verifier_local() -> bool:
    """Contrôle d'intégrité du kit généré (utile avant une copie USB manuelle)."""
    manifest = json.loads((SORTIE / "manifest.json").read_text(encoding="utf-8"))
    return all(sha_fichier(SORTIE / n) == s for n, s in manifest["livres"].items())
