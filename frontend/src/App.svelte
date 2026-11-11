<script>
  // Kit d'urgence : rail à gauche sur PC, pilule d'icônes en bas sur iPhone (format commun).
  import { onMount } from 'svelte'
  import { fly } from 'svelte/transition'
  import LayoutGrid from '@lucide/svelte/icons/layout-grid'
  import LibraryBig from '@lucide/svelte/icons/library-big'
  import Network from '@lucide/svelte/icons/network'
  import SlidersHorizontal from '@lucide/svelte/icons/sliders-horizontal'
  import { api } from '$lib/api.js'
  import Connexion from './pages/Connexion.svelte'
  import ATraiter from './pages/ATraiter.svelte'
  import Kit from './pages/Kit.svelte'
  import Services from './pages/Services.svelte'
  import Reglages from './pages/Reglages.svelte'

  const onglets = [
    { page: 'a-traiter', nom: 'À traiter', icone: LayoutGrid },
    { page: 'kit', nom: 'Kit', icone: LibraryBig },
    { page: 'connexion', nom: 'Connexion', icone: Network },
    { page: 'reglages', nom: 'Réglages', icone: SlidersHorizontal },
  ]

  let connecte = $state(null) // null : on ne sait pas encore
  let session = $state({ version: '', lecture_seule: false })
  let page = $state(lirePage())
  let attente = $state(0) // nombre de choses à traiter, montré sur l'onglet

  function lirePage() {
    const p = location.hash.replace('#/', '').split('/')[0]
    return onglets.some((o) => o.page === p) ? p : 'a-traiter'
  }

  async function verifier() {
    try {
      const s = await api.get('/api/session')
      session = s
      connecte = s.connecte
    } catch {
      connecte = false
    }
  }

  async function deconnecter() {
    try { await api.post('/api/deconnexion') } catch { /* déjà déconnecté */ }
    connecte = false
  }

  const sortir = () => (connecte = false)
  onMount(verifier)
</script>

<svelte:window onhashchange={() => (page = lirePage())} />

{#if connecte === false}
  <Connexion onconnecte={verifier} />
{:else if connecte}
  <div class="md:pl-52">
    <nav
      aria-label="Sections"
      class="fixed bottom-[calc(0.75rem+env(safe-area-inset-bottom))] left-1/2 z-20 flex -translate-x-1/2 items-center gap-1 rounded-full border bg-card/80 p-1.5 shadow-lg backdrop-blur-md
             md:inset-y-0 md:left-0 md:w-52 md:translate-x-0 md:flex-col md:items-stretch md:gap-1 md:rounded-none md:border-0 md:border-r md:bg-transparent md:p-4 md:shadow-none md:backdrop-blur-none"
    >
      <span class="mb-4 hidden px-2 text-xl font-light tracking-tight md:block">Kit d'urgence</span>
      {#each onglets as o}
        {@const Icone = o.icone}
        <a
          href={'#/' + o.page}
          aria-label={o.page === 'a-traiter' && attente ? `${o.nom}, ${attente}` : o.nom}
          aria-current={page === o.page ? 'page' : undefined}
          class="relative flex h-11 items-center gap-2 rounded-full px-4 text-sm font-medium text-muted-foreground transition-colors
                 hover:text-foreground aria-[current=page]:bg-foreground aria-[current=page]:text-background
                 md:h-10 md:rounded-lg md:px-3 md:aria-[current=page]:bg-secondary md:aria-[current=page]:text-foreground"
        >
          <Icone class="size-[1.15rem]" aria-hidden="true" />
          <span class="sr-only md:not-sr-only">{o.nom}</span>
          {#if o.page === 'a-traiter' && attente}
            <span class="absolute -top-0.5 right-1 grid min-w-5 place-items-center rounded-full bg-primary px-1 text-[0.7rem] font-semibold text-primary-foreground
                         md:static md:ml-auto" aria-hidden="true">{attente}</span>
          {/if}
        </a>
      {/each}
    </nav>

    <main
      class="mx-auto max-w-4xl px-[max(1rem,env(safe-area-inset-left))] pt-[calc(1.25rem+env(safe-area-inset-top))] pb-[calc(6rem+env(safe-area-inset-bottom))] md:px-8 md:pt-8 md:pb-10"
    >
      {#if session.lecture_seule}
        <p class="mb-4 rounded-xl border border-primary/50 px-4 py-2 text-sm" role="status">
          Mode lecture seule : le kit fabrique ses livres mais n'écrit ni sur la liseuse ni dans ses sources.
        </p>
      {/if}
      {#key page}
        <div in:fly={{ y: 6, duration: 180 }}>
          {#if page === 'kit'}
            <Kit lectureSeule={session.lecture_seule} ondeconnecte={sortir} />
          {:else if page === 'connexion'}
            <Services lectureSeule={session.lecture_seule} ondeconnecte={sortir} />
          {:else if page === 'reglages'}
            <Reglages {deconnecter} ondeconnecte={sortir} />
          {:else}
            <ATraiter lectureSeule={session.lecture_seule} ondeconnecte={sortir} oncompte={(n) => (attente = n)} />
          {/if}
        </div>
      {/key}
    </main>
  </div>
{/if}
