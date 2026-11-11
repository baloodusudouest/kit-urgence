<script>
  // Papiers : on dépose, on range, on retire. Aucun aperçu, aucun téléchargement du fichier déposé.
  // Un papier retiré est mis de côté : on peut le remettre, ou l'effacer pour de bon.
  import ArrowUp from '@lucide/svelte/icons/arrow-up'
  import ArrowDown from '@lucide/svelte/icons/arrow-down'
  import { api } from '$lib/api.js'
  import { poids, jour } from '$lib/format.js'
  import { Button } from '$lib/components/ui/button/index.js'
  import Depot from './Depot.svelte'

  let { papiers, retires, lectureSeule = false, onchange, onerreur } = $props()
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
         texte="Glisse tes papiers ici" aide="PDF, JPG ou PNG, 50 Mo au plus chacun. Ils sont rangés à la fin du livre."
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
