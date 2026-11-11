<script>
  // « À traiter » : la phrase d'état, puis une tuile par chose à faire. Une tuile à zéro s'efface.
  // Le rouge est la couleur de l'appli : un problème se dit par un pictogramme et un mot.
  import { onMount } from 'svelte'
  import TriangleAlert from '@lucide/svelte/icons/triangle-alert'
  import BookX from '@lucide/svelte/icons/book-x'
  import RefreshCw from '@lucide/svelte/icons/refresh-cw'
  import TabletSmartphone from '@lucide/svelte/icons/tablet-smartphone'
  import Printer from '@lucide/svelte/icons/printer'
  import ClipboardCheck from '@lucide/svelte/icons/clipboard-check'
  import PenLine from '@lucide/svelte/icons/pen-line'
  import PhoneCall from '@lucide/svelte/icons/phone-call'
  import FileQuestion from '@lucide/svelte/icons/file-question'
  import Clock from '@lucide/svelte/icons/clock'
  import Info from '@lucide/svelte/icons/info'
  import { api } from '$lib/api.js'
  import { jour, lienLivre } from '$lib/format.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let { lectureSeule = false, ondeconnecte, oncompte } = $props()

  const DEFS = [
    { cle: 'erreur', nom: 'Erreur', icone: TriangleAlert },
    { cle: 'disparition', nom: 'Livre à retirer ?', icone: BookX },
    { cle: 'modifie', nom: 'Kit à refabriquer', icone: RefreshCw },
    { cle: 'liseuse', nom: 'Liseuse pas à jour', icone: TabletSmartphone },
    { cle: 'papier', nom: 'Papier à réimprimer', icone: Printer },
    { cle: 'essai', nom: 'Essai du kit', icone: ClipboardCheck },
    { cle: 'completer', nom: 'À compléter', icone: PenLine },
    { cle: 'verifier', nom: 'Numéros à vérifier', icone: PhoneCall },
    { cle: 'guides', nom: 'Guides incomplets', icone: FileQuestion },
    { cle: 'silence', nom: 'Sans nouvelles', icone: Clock },
    { cle: 'avertissement', nom: 'À savoir', icone: Info },
  ]

  let d = $state(null)
  let choisie = $state(null)
  let message = $state('')
  let attente = $state('')
  let points = $state({})

  const visibles = $derived(d ? DEFS.filter((t) => d.tuiles[t.cle]?.nombre) : [])
  const t = $derived(d && choisie ? d.tuiles[choisie] : null)

  function recevoir(etat) {
    d = etat
    oncompte?.(etat.total)
    if (choisie && !etat.tuiles[choisie]?.nombre) choisie = null
  }
  async function lire() {
    try { recevoir(await api.get('/api/etat')) } catch (e) { if (e.statut === 401) ondeconnecte?.(); else message = e.message }
  }
  async function geste(nom, chemin, corps, dit) {
    attente = nom; message = ''
    try { recevoir(await api.post(chemin, corps)); message = dit }
    catch (e) { if (e.statut === 401) ondeconnecte?.(); else message = e.message }
    attente = ''
  }
  const essaiComplet = $derived(d ? d.tuiles.essai.points.every((p) => points[p.cle]) : false)
  onMount(lire)
</script>

<header class="mb-5">
  <p class="etiquette">Kit d'urgence</p>
  <h1 class="titre">À traiter</h1>
</header>

{#if !d}
  <p class="text-sm text-muted-foreground">Lecture…</p>
{:else}
  <p class="mb-5 rounded-2xl border bg-card px-5 py-4 text-[1.05rem] leading-snug" role="status" id="phrase">{d.phrase}</p>

  {#if !visibles.length}
    <p class="text-sm text-muted-foreground">Rien à faire aujourd'hui.</p>
  {:else}
    <div class="grid grid-cols-2 gap-3 md:grid-cols-4" role="group" aria-label="Choses à traiter">
      {#each visibles as def}
        {@const Icone = def.icone}
        <button type="button" aria-pressed={choisie === def.cle} onclick={() => { choisie = choisie === def.cle ? null : def.cle; message = '' }}
                class="flex min-h-28 flex-col justify-between gap-2 rounded-2xl border bg-card p-4 text-left transition-colors hover:border-primary aria-pressed:border-primary">
          <span class="flex items-start justify-between">
            <Icone class="size-6 text-primary" aria-hidden="true" />
            <span class="chiffre text-3xl">{d.tuiles[def.cle].nombre}</span>
          </span>
          <span class="nom-tuile font-medium leading-tight">{def.nom}</span>
        </button>
      {/each}
    </div>
  {/if}

  {#if t}
    <section class="mt-4 rounded-2xl border bg-card p-5" aria-label={DEFS.find((x) => x.cle === choisie).nom}>
      {#if choisie === 'erreur'}
        <h2 class="text-lg font-semibold">Quelque chose a échoué</h2>
        <ul class="mt-2 list-disc space-y-1 pl-5 text-sm">{#each t.lignes as l}<li>{l}</li>{/each}</ul>
        <p class="mt-2 text-sm text-muted-foreground">Un livre qui échoue ne remplace jamais le dernier bon : l'ancien reste en place.</p>
        <div class="mt-3"><Button onclick={() => geste('fabriquer', '/api/generer', {}, 'Kit refabriqué.')} disabled={!!attente}>{attente ? 'Fabrication…' : 'Refabriquer'}</Button></div>

      {:else if choisie === 'disparition'}
        <h2 class="text-lg font-semibold">Ce livre n'a plus de source</h2>
        <p class="mt-1 text-sm text-muted-foreground">Le kit ne retire jamais seul un livre : il serait ensuite effacé de la liseuse. Si c'est une erreur
          (papier retiré par mégarde, mot de passe des papiers absent de la stack), corrige la cause et refabrique : le livre reste.</p>
        <ul class="mt-3 space-y-2">
          {#each t.livres as nom}
            <li class="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span>{nom}</span>
              <Button variant="outline" disabled={!!attente || lectureSeule} onclick={() => geste('retirer', '/api/disparitions', { livres: [nom] }, 'Livre retiré du kit. Il quittera la liseuse à la prochaine livraison.')}>Oui, le retirer</Button>
            </li>
          {/each}
        </ul>

      {:else if choisie === 'modifie'}
        <h2 class="text-lg font-semibold">Des sources ont changé</h2>
        <p class="mt-1 text-sm text-muted-foreground">Un texte, un contact, un papier ou un réglage a changé depuis la dernière fabrication. Les livres seront refaits
          maintenant, ou tout seuls quand la liseuse se présentera.</p>
        <div class="mt-3"><Button onclick={() => geste('fabriquer', '/api/generer', {}, 'Kit refabriqué.')} disabled={!!attente}>{attente ? 'Fabrication…' : 'Fabriquer les livres'}</Button></div>

      {:else if choisie === 'liseuse'}
        <h2 class="text-lg font-semibold">La liseuse n'a pas le dernier kit</h2>
        {#if !t.reglee}
          <p class="mt-1 text-sm text-muted-foreground">L'adresse de la liseuse n'est pas réglée (fichier de réglages du kit).</p>
        {:else if t.joignable}
          <p class="mt-1 text-sm text-muted-foreground">Elle répond. Livrer envoie les livres qui ont changé, puis relit chacun sur la liseuse pour vérifier.</p>
          <div class="mt-3"><Button onclick={() => geste('livrer', '/api/livrer', {}, 'Livraison faite et vérifiée.')} disabled={!!attente || lectureSeule}>{attente ? 'Livraison…' : 'Livrer'}</Button></div>
        {:else}
          <ol class="mt-2 list-decimal space-y-1 pl-5 text-sm">
            <li>Allume la liseuse et ouvre KOReader.</li>
            <li>Active le Wi-Fi, puis dans le menu Outils › Plus d'outils › SSH, démarre le serveur SSH.</li>
            <li>Laisse-la allumée une minute : le kit la voit et livre tout seul.</li>
          </ol>
        {/if}

      {:else if choisie === 'papier'}
        <h2 class="text-lg font-semibold">La version papier a changé</h2>
        {#if t.changements === null}
          <p class="mt-1 text-sm text-muted-foreground">Elle n'a jamais été marquée imprimée.</p>
        {:else if t.changements.length}
          <p class="mt-1 text-sm text-muted-foreground">Changé depuis la dernière impression — à toi de juger si ça vaut une réimpression :</p>
          <ul class="mt-1 list-disc pl-5 text-sm">{#each t.changements as c}<li>{c}</li>{/each}</ul>
        {:else}
          <p class="mt-1 text-sm text-muted-foreground">Le contenu est le même qu'à la dernière impression ; seule la mise en page a été refaite.</p>
        {/if}
        <div class="mt-3 flex flex-wrap items-center gap-2">
          <a class="inline-flex h-9 items-center rounded-md border px-4 text-sm font-medium hover:bg-accent" href={lienLivre('kit-urgence-a-imprimer.pdf')} download>Télécharger le PDF</a>
          <Button onclick={() => geste('papier', '/api/papier/imprime', {}, 'Noté : la version papier est à jour.')} disabled={!!attente}>Papier imprimé</Button>
        </div>

      {:else if choisie === 'essai'}
        <h2 class="text-lg font-semibold">Essayer le kit en vrai</h2>
        <p class="mt-1 text-sm text-muted-foreground">
          {t.le ? `Dernier essai le ${jour(t.le)}.` : 'Le kit n\'a jamais été essayé.'}
          {t.mot_de_passe_change ? ' Le mot de passe des papiers a changé depuis : à réessayer.' : ''}
          La machine vérifie que les livres s'ouvrent ; elle ne peut pas vérifier que toi, tu y arrives. Tous les six mois, liseuse en main :
        </p>
        <ul class="mt-3 space-y-2">
          {#each t.points as p}
            <li><label class="flex min-h-11 items-start gap-3 text-sm">
              <input type="checkbox" class="mt-0.5 size-5 flex-none accent-[var(--app)]" bind:checked={points[p.cle]} />
              <span>{p.texte}</span></label></li>
          {/each}
        </ul>
        <div class="mt-3"><Button onclick={() => geste('essai', '/api/essai', { points }, 'Essai noté.')} disabled={!!attente || !essaiComplet}>Noter l'essai</Button></div>

      {:else if choisie === 'completer'}
        <h2 class="text-lg font-semibold">Passages « À COMPLÉTER »</h2>
        <ul class="mt-2 space-y-1 text-sm">
          {#each t.lignes as l}<li>{l.ou === 'texte' ? `Texte « ${l.titre} »` : `Numéro « ${l.nom} » (${l.titre})`}{l.nombre > 1 ? ` — ${l.nombre} passages` : ''}</li>{/each}
        </ul>
        <p class="mt-3 text-sm"><a class="underline" href="#/kit">Ouvrir le kit</a></p>

      {:else if choisie === 'verifier'}
        <h2 class="text-lg font-semibold">Numéros jamais vérifiés</h2>
        <p class="mt-1 text-sm text-muted-foreground">À contrôler sur une facture ou le site officiel.</p>
        <ul class="mt-2 space-y-1 text-sm">{#each t.lignes as l}<li><strong class="font-medium">{l.nom}</strong> : {l.numero}</li>{/each}</ul>
        <p class="mt-3 text-sm"><a class="underline" href="#/kit">Ouvrir le kit</a></p>

      {:else if choisie === 'guides'}
        <h2 class="text-lg font-semibold">Guides qui ne partent pas dans le kit</h2>
        <ul class="mt-2 space-y-1 text-sm">{#each t.lignes as g}<li><strong class="font-medium">{g.titre}</strong> — il manque : {g.manques.join(', ')}</li>{/each}</ul>
        <p class="mt-3 text-sm"><a class="underline" href="#/kit">Ouvrir le kit</a></p>

      {:else}
        <h2 class="text-lg font-semibold">{DEFS.find((x) => x.cle === choisie).nom}</h2>
        <ul class="mt-2 list-disc space-y-1 pl-5 text-sm">{#each t.lignes as l}<li>{l}</li>{/each}</ul>
      {/if}
      {#if lectureSeule && ['disparition', 'liseuse'].includes(choisie)}<p class="mt-2 text-sm text-muted-foreground">Lecture seule : ce geste est refusé.</p>{/if}
    </section>
  {/if}
  {#if message}<p class="mt-3 text-sm" role="status" id="message">{message}</p>{/if}
{/if}
