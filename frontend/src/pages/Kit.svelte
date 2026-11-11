<script>
  // « Kit » : les livres dans l'ordre de la liseuse, nommés par ce qu'ils contiennent.
  // 2.1.0 : on y écrit les textes, on y corrige les numéros, on y dépose papiers et guides.
  // Enregistrer ne fabrique rien : le kit passe « à refabriquer ».
  import { onMount } from 'svelte'
  import Lock from '@lucide/svelte/icons/lock'
  import TriangleAlert from '@lucide/svelte/icons/triangle-alert'
  import { api } from '$lib/api.js'
  import { quand, poids, lienLivre } from '$lib/format.js'
  import { Button } from '$lib/components/ui/button/index.js'
  import Textes from '$lib/kit/Textes.svelte'
  import Numeros from '$lib/kit/Numeros.svelte'
  import Papiers from '$lib/kit/Papiers.svelte'
  import Guides from '$lib/kit/Guides.svelte'

  let { lectureSeule = false, ondeconnecte, cible = [] } = $props()
  let d = $state(null)
  let ouvert = $state(null)
  let message = $state('')
  let attente = $state('')

  const refus = (e) => { if (e.statut === 401) ondeconnecte?.(); else message = e.message }
  async function lire() { try { d = await api.get('/api/livres') } catch (e) { refus(e) } }
  async function geste(nom, chemin, dit) {
    attente = nom; message = ''
    try { await api.post(chemin); message = dit; await lire() } catch (e) { refus(e) }
    attente = ''
  }
  // Adresse « #/kit/02 » ou « #/kit/01/10-electricite.md » : le livre (et le texte) s'ouvrent tout seuls
  function suivreCible() {
    if (!d || !cible.length) return
    const livre = d.livres.find((l) => l.numero === cible[0])
    if (livre) ouvert = livre.fichier
    if (cible[0] === '04') document.getElementById('guides')?.scrollIntoView()
  }
  onMount(async () => { await lire(); suivreCible() })
</script>

<header class="mb-5">
  <p class="etiquette">Kit d'urgence</p>
  <h1 class="titre">Kit</h1>
</header>

<section class="mb-5 grid gap-3 md:grid-cols-2" aria-label="Fabriquer et livrer">
  <div class="rounded-2xl border bg-card p-4">
    <Button variant="outline" onclick={() => geste('fabriquer', '/api/generer', 'Livres refaits là où il le fallait.')} disabled={!!attente}>{attente === 'fabriquer' ? 'Fabrication…' : 'Fabriquer'}</Button>
    <p class="mt-2 text-sm text-muted-foreground">Refait, sur le NAS, les livres dont une source a changé. Chaque livre est rouvert pour vérifier qu'il se lit.</p>
  </div>
  <div class="rounded-2xl border bg-card p-4">
    <Button onclick={() => geste('livrer', '/api/livrer', 'Livraison faite et vérifiée.')} disabled={!!attente || lectureSeule}>{attente === 'livrer' ? 'Livraison…' : 'Livrer'}</Button>
    <p class="mt-2 text-sm text-muted-foreground">Envoie les livres sur la liseuse, puis relit chacun là-bas. Elle doit être allumée, KOReader ouvert.</p>
  </div>
</section>
{#if message}<p class="mb-4 text-sm" role="status" id="message">{message}</p>{/if}

{#if !d}
  <p class="text-sm text-muted-foreground">Lecture…</p>
{:else}
  <ul class="space-y-3" aria-label="Livres">
    {#each d.livres as l (l.fichier)}
      <li class="rounded-2xl border bg-card">
        <button type="button" class="flex w-full items-center gap-4 p-4 text-left" aria-expanded={ouvert === l.fichier}
                onclick={() => (ouvert = ouvert === l.fichier ? null : l.fichier)}>
          <span class="tranche w-16 flex-none" aria-hidden="true">{l.numero}</span>
          <span class="min-w-0 flex-1">
            <span class="flex items-center gap-2 text-lg font-semibold leading-tight">{l.titre}
              {#if l.chiffre}<Lock class="size-4 text-muted-foreground" aria-label="chiffré" />{/if}</span>
            <span class="block text-sm text-muted-foreground">{l.quoi}</span>
            {#if l.echec}<span class="mt-1 flex items-center gap-1.5 text-sm font-medium"><TriangleAlert class="size-4" aria-hidden="true" />Dernière fabrication refusée : {l.echec}</span>{/if}
            {#if l.va_disparaitre}<span class="mt-1 flex items-center gap-1.5 text-sm font-medium"><TriangleAlert class="size-4" aria-hidden="true" />N'a plus de source : voir « À traiter »</span>{/if}
          </span>
        </button>
        {#if ouvert === l.fichier}
          <div class="border-t px-4 py-4 text-sm">
            <p class="flex flex-wrap items-center justify-between gap-2 text-muted-foreground">
              <span>{l.present ? `Fabriqué le ${quand(l.fabrique_le)} · ${poids(l.poids)}` : 'Pas encore fabriqué'}</span>
              {#if l.present}<a class="inline-flex h-9 items-center rounded-md border px-4 font-medium text-foreground hover:bg-accent" href={lienLivre(l.fichier)} download>Télécharger{l.chiffre ? ' (chiffré)' : ''}</a>{/if}
            </p>

            {#if l.numero === '00' || l.numero === '01'}
              <Textes livre={l.numero} textes={d.textes} {lectureSeule} onchange={lire} onerreur={refus} ouvrir={cible[0] === l.numero ? cible[1] : null} />

            {:else if l.numero === '02'}
              <p class="mt-3 text-muted-foreground">Les contacts viennent de carnet (groupe Urgence), reçus le {quand(d.recus_le)}. Ils se modifient dans carnet.</p>
              <ul class="mt-2 divide-y" aria-label="Contacts">
                {#each d.contacts as c}
                  <li class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 py-2">
                    <span><span class="font-medium">{c.nom}</span> <span class="text-muted-foreground">{c.tels.join(' · ')}</span></span>
                    {#if c.carnet}<a class="underline" href={c.carnet} target="_blank" rel="noopener">Ouvrir dans carnet</a>{/if}
                  </li>
                {:else}<li class="py-2 text-muted-foreground">Aucun contact reçu.</li>{/each}
              </ul>
              <Numeros numeros={d.numeros} {lectureSeule} onchange={lire} onerreur={refus} />

            {:else if l.numero === '05'}
              <Papiers papiers={d.papiers} retires={d.retires} {lectureSeule} onchange={lire} onerreur={refus} />

            {:else if l.papier}
              <p class="mt-3 text-muted-foreground">À imprimer et à ranger avec la liseuse. Le mot de passe des papiers n'y figure pas : il est sur la fiche manuscrite, rangée à part.</p>
            {/if}
          </div>
        {/if}
      </li>
    {/each}
  </ul>

  <section id="guides" class="mt-5 rounded-2xl border bg-card p-5" aria-label="Guides officiels">
    <h2 class="flex items-baseline gap-3"><span class="tranche text-3xl" aria-hidden="true">04</span><span class="text-lg font-semibold">Guides officiels</span></h2>
    <p class="mt-1 text-sm text-muted-foreground">Copiés sans modification. Un guide ne part dans le kit que s'il a son fichier, son éditeur et son adresse officielle.</p>
    <Guides guides={d.guides} {lectureSeule} onchange={lire} onerreur={refus} />
  </section>
{/if}
