<script>
  // « Réglages » : ce qui n'est pas un service. En bas : le journal, la version, la déconnexion.
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'
  import { quand } from '$lib/format.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let { deconnecter, ondeconnecte } = $props()
  let d = $state(null)
  let message = $state('')
  async function lire() { try { d = await api.get('/api/reglages') } catch (e) { if (e.statut === 401) ondeconnecte?.(); else message = e.message } }
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
    <dl class="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
      <dt class="text-muted-foreground">Nom du foyer</dt><dd>{d.titre_foyer}</dd>
      <dt class="text-muted-foreground">Liseuse</dt><dd>{d.liseuse.host ? `${d.liseuse.host}:${d.liseuse.port}` : 'adresse non réglée'}</dd>
      <dt class="text-muted-foreground">Dossier sur la liseuse</dt><dd>{d.liseuse.dossier}</dd>
      <dt class="text-muted-foreground">Recherche de la liseuse</dt><dd>toutes les {d.scrutation_secondes} secondes</dd>
      <dt class="text-muted-foreground">Mot de passe des papiers</dt><dd>{d.mot_de_passe_papiers ? 'réglé dans la stack' : 'absent de la stack : le livre des papiers n\'est pas fabriqué'}</dd>
    </dl>
    <p class="mt-3 text-sm text-muted-foreground">Le mot de passe des papiers ne s'affiche pas et ne se change pas ici : il vit dans la stack, et sur la fiche manuscrite rangée à part.</p>
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
