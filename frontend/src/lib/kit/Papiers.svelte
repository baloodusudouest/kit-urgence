<script>
  // Papiers : on dépose, on range, on retire. Aucun aperçu, aucun téléchargement du fichier déposé.
  // Un papier retiré est mis de côté : on peut le remettre, ou l'effacer pour de bon.
  import ArrowUp from '@lucide/svelte/icons/arrow-up'
  import ArrowDown from '@lucide/svelte/icons/arrow-down'
  import { api } from '$lib/api.js'
  import { poids, jour } from '$lib/format.js'
  import { Button } from '$lib/components/ui/button/index.js'
  import Depot from './Depot.svelte'
  import Check from '@lucide/svelte/icons/check'

  let { papiers, pieces = [], retires, lectureSeule = false, onchange, onerreur } = $props()
  let message = $state('')
  let attente = $state(false)
  let renomme = $state(null)    // { nom, nouveau }
  let aEffacer = $state(null)

  async function essayer(faire, dit) {
    attente = true; message = ''
    try { await faire(); await onchange?.(); message = dit } catch (e) { if (e.statut === 401) onerreur?.(e); else { message = e.message; onchange?.() } }
    attente = false
  }
  const deposer = (fichiers) => essayer(async () => {
    for (const f of fichiers) await api.deposer('/api/papiers', f)
  }, `${fichiers.length} fichier(s) déposé(s), rangé(s) à la fin du livre. Le livre sera refait à la prochaine fabrication.`)
  // 2.2.0 : les papiers conseillés. Déposer depuis une ligne donne au fichier le nom de la ligne.
  const ACCEPTES = ['.pdf', '.jpg', '.jpeg', '.png']
  const groupes = $derived([...new Set(pieces.map((p) => p.groupe))])
  const aFaire = $derived(pieces.filter((p) => !p.ecartee && !p.papiers.length).length)
  const concernees = $derived(pieces.filter((p) => !p.ecartee).length)
  let survol = $state('')       // 2.2.1 : ligne au-dessus de laquelle on tient un fichier
  const libre = (p) => !p.ecartee && !attente && !lectureSeule
  function lacher(e, p) {
    e.preventDefault(); survol = ''
    if (libre(p) && e.dataTransfer?.files?.length) deposerPour(p, e.dataTransfer.files)
  }
  function deposerPour(piece, fichiers, entree) {
    const f = [...fichiers].filter((x) => ACCEPTES.some((e) => x.name.toLowerCase().endsWith(e)))
    if (entree) entree.value = ''
    if (!f.length) { message = 'Seuls PDF, JPG et PNG sont acceptés.'; return }
    return essayer(async () => { for (const x of f) await api.deposer('/api/papiers', x, { piece: piece.cle }) },
      `« ${piece.nom} » : ${f.length} fichier(s) déposé(s). Le livre sera refait à la prochaine fabrication.`)
  }
  const ecarter = (piece, oui) => essayer(() => api.post('/api/papiers/conseille', { cle: piece.cle, ecartee: oui }),
    oui ? `« ${piece.nom} » ne te sera plus proposé.` : `« ${piece.nom} » est de nouveau proposé.`)
  const deplacer = (i, pas) => {
    const noms = papiers.map((p) => p.nom)
    ;[noms[i], noms[i + pas]] = [noms[i + pas], noms[i]]
    return essayer(() => api.post('/api/papiers/ordre', { noms }), 'Ordre changé.')
  }
  const renommer = () => essayer(async () => { await api.post('/api/papiers/renommer', renomme); renomme = null }, 'Papier renommé.')
  const retirer = (nom) => essayer(() => api.post('/api/papiers/retirer', { nom }),
    'Papier mis de côté. Il reste dans l\'ancien livre, sur le NAS et sur la liseuse, tant que le kit n\'a pas été refabriqué puis livré.')
  const remettre = (id) => essayer(() => api.post('/api/papiers/remettre', { id }), 'Papier remis dans le livre.')
  const effacer = (id) => essayer(async () => { await api.post('/api/papiers/effacer', { id }); aEffacer = null }, 'Papier effacé du dossier du kit.')
</script>

{#if pieces.length}
  <h3 class="etiquette mt-4">Papiers à toujours avoir sur soi</h3>
  <p class="mt-1 text-muted-foreground">Une copie de chacun : glisse le fichier sur sa ligne, ou touche « Déposer ». {concernees - aFaire} sur {concernees} dans le livre. Une ligne se coche toute seule quand un papier déposé porte son nom. Rien n'est obligatoire : écarte ce qui ne te concerne pas.</p>
  {#each groupes as g}
    <h4 class="mt-3 text-sm font-medium text-muted-foreground">{g}</h4>
    <ul class="divide-y" aria-label={'Papiers conseillés : ' + g}>
      {#each pieces.filter((p) => p.groupe === g) as p (p.cle)}
        <li class="ligne flex flex-wrap items-center justify-between gap-2 py-2" class:opacity-60={p.ecartee} class:survol={survol === p.cle}
            ondragenter={(e) => { e.preventDefault(); if (libre(p)) survol = p.cle }}
            ondragover={(e) => { e.preventDefault(); if (libre(p)) survol = p.cle }}
            ondragleave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) survol = '' }}
            ondrop={(e) => lacher(e, p)}>
          <span class="flex min-w-0 items-start gap-2">
            {#if p.papiers.length}<Check class="mt-0.5 size-4 flex-none text-primary" aria-hidden="true" />{:else}<span class="mt-0.5 size-4 flex-none rounded-full border border-input" aria-hidden="true"></span>{/if}
            <span class="min-w-0">
              <span class="font-medium">{p.nom}</span>
              <span class="block break-all text-sm text-muted-foreground">{survol === p.cle ? 'Lâche ici' : p.ecartee ? 'Pas concerné' : p.papiers.length ? 'Dans le livre : ' + p.papiers.join(', ') : 'À déposer'}</span>
            </span>
          </span>
          <span class="flex flex-wrap items-center gap-1.5">
            {#if p.ecartee}
              <Button variant="outline" onclick={() => ecarter(p, false)} disabled={attente || lectureSeule}>Proposer de nouveau</Button>
            {:else}
              <label class="deposer" class:inactif={attente || lectureSeule}>{p.papiers.length ? 'Ajouter une page' : 'Déposer'}
                <input type="file" multiple accept={ACCEPTES.join(',')} disabled={attente || lectureSeule} aria-label={'Déposer : ' + p.nom}
                       onchange={(e) => e.currentTarget.files.length && deposerPour(p, e.currentTarget.files, e.currentTarget)} /></label>
              {#if !p.papiers.length}<Button variant="outline" onclick={() => ecarter(p, true)} disabled={attente || lectureSeule} aria-label={'Pas concerné : ' + p.nom}>Pas concerné</Button>{/if}
            {/if}
          </span>
        </li>
      {/each}
    </ul>
  {/each}
  <h3 class="etiquette mt-5">Dans le livre</h3>
{/if}
<p class="mt-3 text-muted-foreground">Dans l'ordre du livre. Les papiers ne s'affichent pas et ne se téléchargent pas ici : seul le livre chiffré sort.</p>
<ol class="mt-2 divide-y" aria-label="Papiers">
  {#each papiers as p, i (p.nom)}
    <li class="py-2">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <span class="min-w-0 break-all"><span class="text-muted-foreground">{i + 1}.</span> {p.nom} <span class="text-muted-foreground">· {poids(p.poids)}</span></span>
        <span class="flex flex-wrap gap-1.5">
          <Button variant="outline" size="icon" aria-label={`Monter ${p.nom}`} onclick={() => deplacer(i, -1)} disabled={attente || lectureSeule || i === 0}><ArrowUp class="size-4" /></Button>
          <Button variant="outline" size="icon" aria-label={`Descendre ${p.nom}`} onclick={() => deplacer(i, 1)} disabled={attente || lectureSeule || i === papiers.length - 1}><ArrowDown class="size-4" /></Button>
          <Button variant="outline" onclick={() => (renomme = { nom: p.nom, nouveau: p.nom.replace(/^\d+-/, '').replace(/\.[^.]+$/, '') })} disabled={lectureSeule}>Renommer</Button>
          <Button variant="outline" onclick={() => retirer(p.nom)} disabled={attente || lectureSeule}>Retirer</Button>
        </span>
      </div>
      {#if renomme?.nom === p.nom}
        <form class="mt-2 flex flex-wrap items-end gap-2" onsubmit={(e) => { e.preventDefault(); renommer() }}>
          <label class="flex min-w-40 flex-1 flex-col gap-1 text-sm">Nouveau nom
            <input bind:value={renomme.nouveau} required maxlength="80" class="h-10 rounded-lg border border-input bg-background px-3 outline-none focus:border-ring" /></label>
          <Button type="submit" disabled={attente}>Renommer</Button>
          <Button variant="outline" onclick={() => (renomme = null)}>Annuler</Button>
        </form>
      {/if}
    </li>
  {:else}<li class="py-2 text-muted-foreground">Aucun papier déposé.</li>{/each}
</ol>

<div class="mt-3">
  <Depot nom="Déposer des papiers" multiple accepte={['.pdf', '.jpg', '.jpeg', '.png']} desactive={attente || lectureSeule}
         texte="Glisse tes papiers ici" aide="Tout autre papier : PDF, JPG ou PNG, 50 Mo au plus chacun. Ils sont rangés à la fin du livre."
         onfichiers={deposer} />
</div>
{#if attente}<p class="mt-2 text-sm text-muted-foreground">En cours…</p>{/if}
{#if message}<p class="mt-2 text-sm" role="status" id="message-papiers">{message}</p>{/if}

{#if retires.length}
  <h3 class="etiquette mt-5">Mis de côté ({retires.length})</h3>
  <p class="mt-1 text-muted-foreground">Ces papiers ne sont plus dans le livre mais sont toujours sur le NAS.</p>
  <ul class="mt-1 divide-y" aria-label="Papiers mis de côté">
    {#each retires as r (r.id)}
      <li class="flex flex-wrap items-center justify-between gap-2 py-2">
        <span class="min-w-0 break-all">{r.nom} <span class="text-muted-foreground">· retiré le {jour(r.retire_le)}</span></span>
        <span class="flex flex-wrap items-center gap-1.5">
          {#if aEffacer === r.id}
            <span>Effacer pour de bon ?</span>
            <Button variant="outline" onclick={() => effacer(r.id)} disabled={attente || lectureSeule}>Oui, effacer</Button>
            <Button variant="outline" onclick={() => (aEffacer = null)}>Non</Button>
          {:else}
            <Button variant="outline" onclick={() => remettre(r.id)} disabled={attente || lectureSeule}>Remettre</Button>
            <Button variant="outline" onclick={() => (aEffacer = r.id)} disabled={lectureSeule}>Effacer définitivement…</Button>
          {/if}
        </span>
      </li>
    {/each}
  </ul>
  <p class="mt-1 text-sm text-muted-foreground">Effacer supprime le fichier du dossier du kit. La corbeille du NAS et les sauvegardes peuvent en garder une copie.</p>
{/if}

<style>
  .ligne { border-radius: 0.6rem; }
  .ligne.survol { outline: 2px solid var(--app); outline-offset: 2px; background: color-mix(in srgb, var(--app) 10%, var(--background)); }
  .deposer { position: relative; display: inline-flex; align-items: center; min-height: 2.5rem; padding: 0 0.9rem; border-radius: 0.5rem; cursor: pointer;
             background: var(--primary); color: var(--primary-foreground); font-size: 0.875rem; font-weight: 500; }
  .deposer:focus-within { outline: 2px solid var(--ring); outline-offset: 2px; }
  .deposer.inactif { opacity: 0.5; cursor: not-allowed; }
  .deposer input { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
</style>
