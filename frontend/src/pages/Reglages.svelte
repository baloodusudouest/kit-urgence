<script>
  // « Réglages » : ce qui n'est pas un service. En bas : le journal, la version, la déconnexion.
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

  <section class="mt-4 rounded-2xl border bg-card p-5" aria-label="Écriture">
    <h2 class="text-lg font-semibold">Écriture</h2>
    <p class="mt-1 text-sm text-muted-foreground">
      {d.lecture_seule
        ? 'Lecture seule : le kit fabrique ses livres mais n\'écrit ni sur la liseuse ni dans ses sources. À retirer dans la stack (KIT_LECTURE_SEULE) quand tout va bien.'
        : 'Le kit écrit normalement. Pour le premier jour d\'une nouvelle version : KIT_LECTURE_SEULE=1 dans la stack.'}
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
