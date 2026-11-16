<script>
  // « Réglages » : ce qui n'est pas un service. En bas : le journal, la version, la déconnexion.
  // 2.5.1 (choix de Julien) : en lecture seule, les réglages du kit ne se changent ni ne se restaurent, comme avant.
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'
  import { quand } from '$lib/format.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let { deconnecter, ondeconnecte } = $props()
  let d = $state(null)
  let message = $state('')
  let f = $state(null)          // formulaire : copie des réglages, envoyée d'un bloc
  let attente = $state(false)
  function recevoir(r) {
    d = r
    f = { titre_foyer: r.titre_foyer, scrutation_secondes: r.scrutation_secondes, liseuse: { ...r.liseuse } }
  }
  async function lire() { try { recevoir(await api.get('/api/reglages')) } catch (e) { if (e.statut === 401) ondeconnecte?.(); else message = e.message } }
  async function enregistrer(e) {
    e.preventDefault(); attente = true; message = ''
    try { recevoir(await api.put('/api/reglages', f)); message = 'Réglages enregistrés. L\'ancien fichier est gardé dans les versions.' }
    catch (err) { if (err.statut === 401) ondeconnecte?.(); else message = err.message }
    attente = false
  }
  const champ = 'h-10 rounded-lg border border-input bg-background px-3 outline-none focus:border-ring'

  // ---- Restaurer les réglages (sauvegarde gardée chaque nuit par l'Anneau)
  const NOMS = { titre_foyer: 'Nom du foyer', liseuse_adresse: 'Adresse de la liseuse', liseuse_port: 'Port SSH',
    liseuse_dossier: 'Dossier sur la liseuse', scrutation_secondes: 'Recherche de la liseuse (s)' }
  let dates = $state(null)       // null : pas encore demandé
  let choix = $state('')
  let apercu = $state(null)      // { le, version, differences }
  let rmessage = $state('')
  let rattente = $state(false)
  function valeur(v) { return v === '' || v === null || v === undefined ? '(vide)' : String(v) }
  function erreur(err) { if (err.statut === 401) ondeconnecte?.(); else rmessage = err.message }
  async function chercherDates() {
    rattente = true; rmessage = ''; apercu = null
    try { dates = (await api.get('/api/restaurer')).dates; choix = dates[0] || ''; if (!dates.length) rmessage = 'L\'Anneau n\'a encore aucune sauvegarde du kit.' }
    catch (err) { dates = null; erreur(err) }
    rattente = false
  }
  async function voir() {
    if (!choix) return
    rattente = true; rmessage = ''; apercu = null
    try { apercu = await api.get(`/api/restaurer?le=${encodeURIComponent(choix)}`); if (!apercu.differences.length) rmessage = 'Rien à restaurer : les réglages sont déjà ceux de cette sauvegarde.' }
    catch (err) { erreur(err) }
    rattente = false
  }
  async function restaurer() {
    rattente = true; rmessage = ''
    try { const r = await api.post('/api/restaurer', { le: apercu.le }); recevoir(r); rmessage = `Réglages restaurés depuis la sauvegarde du ${r.le}.`; apercu = null }
    catch (err) { erreur(err) }
    rattente = false
  }
  onMount(lire)
</script>

<header class="mb-5">
  <p class="etiquette">Kit d'urgence</p>
  <h1 class="titre">Réglages</h1>
</header>

{#if !d}
  <p class="text-sm text-muted-foreground">{message || 'Lecture…'}</p>
{:else}
  <section class="rounded-2xl border bg-card p-5" aria-label="Réglages du kit">
    <h2 class="text-lg font-semibold">Le kit</h2>
    <form class="mt-3 grid gap-3 text-sm md:grid-cols-2" onsubmit={enregistrer}>
      <label class="flex flex-col gap-1 md:col-span-2">Nom du foyer (sur la page de garde de chaque livre)
        <input bind:value={f.titre_foyer} required maxlength="80" disabled={d.lecture_seule} class={champ} /></label>
      <label class="flex flex-col gap-1">Adresse de la liseuse (IP fixe)
        <input bind:value={f.liseuse.host} maxlength="100" placeholder="192.168.1.50" disabled={d.lecture_seule} class={champ} /></label>
      <label class="flex flex-col gap-1">Port du serveur SSH de KOReader
        <input type="number" min="1" max="65535" bind:value={f.liseuse.port} required disabled={d.lecture_seule} class={champ} /></label>
      <label class="flex flex-col gap-1 md:col-span-2">Dossier des livres sur la liseuse
        <input bind:value={f.liseuse.dossier} required maxlength="200" disabled={d.lecture_seule} class={champ} />
        <span class="text-muted-foreground">La livraison y efface les livres qui ne sont plus dans le kit : un dossier réservé au kit.</span></label>
      <label class="flex flex-col gap-1">Recherche de la liseuse, toutes les (secondes)
        <input type="number" min="15" max="3600" bind:value={f.scrutation_secondes} required disabled={d.lecture_seule} class={champ} /></label>
      <div class="flex items-end"><Button type="submit" disabled={attente || d.lecture_seule}>Enregistrer</Button></div>
    </form>
    {#if message}<p class="mt-2 text-sm" role="status" id="message">{message}</p>{/if}
    <p class="mt-4 text-sm">Mot de passe des papiers : {d.mot_de_passe_papiers ? 'réglé dans la stack' : 'absent de la stack — le livre des papiers n\'est pas fabriqué'}.</p>
    <p class="mt-1 text-sm text-muted-foreground">Le mot de passe des papiers ne s'affiche pas et ne se change pas ici : il vit dans la stack, et sur la fiche manuscrite rangée à part.</p>
  </section>

  <section class="mt-4 rounded-2xl border bg-card p-5" aria-label="Restaurer les réglages">
    <h2 class="text-lg font-semibold">Restaurer les réglages</h2>
    <p class="mt-1 text-sm text-muted-foreground">L'Anneau garde chaque nuit les réglages ci-dessus (ni papiers, ni clé SSH, ni mot de passe). Choisis une date, regarde ce qui changerait, puis confirme.</p>
    {#if !d.sauvegarde_possible}
      <p class="mt-2 text-sm">Le jeton commun (MAISON_JETON) n'est pas dans la stack : pas de sauvegarde chez l'Anneau.</p>
    {:else}
      <div class="mt-3 flex flex-wrap items-end gap-3 text-sm">
        {#if dates === null}
          <Button variant="outline" onclick={chercherDates} disabled={rattente}>Voir les sauvegardes</Button>
        {:else if dates.length}
          <label class="flex min-w-0 flex-col gap-1">Sauvegarde du
            <select bind:value={choix} onchange={() => (apercu = null)} class={champ} id="date-sauvegarde">
              {#each dates as j}<option value={j}>{j}</option>{/each}
            </select></label>
          <Button variant="outline" onclick={voir} disabled={rattente || !choix}>Voir les différences</Button>
        {/if}
      </div>
      {#if apercu?.differences.length}
        <ul class="mt-3 divide-y text-sm" aria-label="Différences">
          {#each apercu.differences as x}
            <li class="flex flex-wrap justify-between gap-x-4 py-1.5">
              <span>{NOMS[x.cle] || x.cle}</span>
              <span class="min-w-0 break-all text-muted-foreground">{valeur(x.actuel)} → <strong class="text-foreground">{valeur(x.sauve)}</strong></span>
            </li>
          {/each}
        </ul>
        <div class="mt-3"><Button onclick={restaurer} disabled={rattente || d.lecture_seule}>Restaurer ces réglages</Button></div>
      {/if}
    {/if}
    {#if rmessage}<p class="mt-2 text-sm" role="status" id="message-restaurer">{rmessage}</p>{/if}
  </section>

  <section class="mt-4 rounded-2xl border bg-card p-5" aria-label="Écriture">
    <h2 class="text-lg font-semibold">Écriture</h2>
    <p class="mt-1 text-sm text-muted-foreground">
      {d.lecture_seule
        ? (d.lecture_seule_origine === 'maison'
          ? 'Lecture seule pour toute la maison : le kit fabrique ses livres mais n\'écrit ni sur la liseuse ni dans ses sources, ni dans ses réglages. À retirer dans la stack (MAISON_LECTURE_SEULE) quand tout va bien, ou KIT_LECTURE_SEULE=non pour que le kit seul écrive.'
          : 'Lecture seule pour cette appli : le kit fabrique ses livres mais n\'écrit ni sur la liseuse ni dans ses sources, ni dans ses réglages. À retirer dans la stack (KIT_LECTURE_SEULE) quand tout va bien.')
        : 'Le kit écrit normalement. Pour le premier jour d\'une nouvelle version : KIT_LECTURE_SEULE=1 (le kit seul) ou MAISON_LECTURE_SEULE=oui (toute la maison) dans la stack.'}
    </p>
  </section>

  <section class="mt-4 rounded-2xl border bg-card p-5" aria-label="Journal">
    <h2 class="text-lg font-semibold">Journal</h2>
    <ul class="mt-2 divide-y text-sm">
      {#each d.journal as l}
        <li class="flex flex-wrap justify-between gap-x-4 py-1.5"><span>{l.quoi}</span><span class="text-muted-foreground">{quand(l.le)} · {l.par}</span></li>
      {:else}<li class="py-1.5 text-muted-foreground">Rien pour l'instant.</li>{/each}
    </ul>
  </section>

  <p class="mt-6 flex items-center justify-between gap-3 text-sm text-muted-foreground">
    <span>Kit d'urgence {d.version}</span>
    <Button variant="outline" onclick={deconnecter}>Se déconnecter</Button>
  </p>
{/if}
