<script>
  // Guides officiels : un guide n'entre qu'avec son titre, son éditeur et son adresse officielle.
  import TriangleAlert from '@lucide/svelte/icons/triangle-alert'
  import { api } from '$lib/api.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let { guides, lectureSeule = false, onchange, onerreur } = $props()
  const VIDE = { titre: '', editeur: '', url: '', date: '', langue: 'fr' }
  let edition = $state(null)    // { indice (null = nouveau), ...fiche }
  let fichier = $state(null)
  let aRetirer = $state(null)
  let message = $state('')
  let attente = $state(false)

  async function essayer(faire, dit) {
    attente = true; message = ''
    try { await faire(); message = dit; onchange?.() } catch (e) { if (e.statut === 401) onerreur?.(e); else message = e.message }
    attente = false
  }
  const fiche = () => ({ titre: edition.titre, editeur: edition.editeur, url: edition.url, date: edition.date, langue: edition.langue })
  const enregistrer = () => essayer(async () => {
    if (edition.indice === null) await api.deposer('/api/guides/fichier', fichier, fiche())
    else await api.put(`/api/guides/${edition.indice}`, fiche())
    edition = null; fichier = null
  }, 'Guide enregistré. Il partira dans le kit à la prochaine fabrication.')
  const joindre = (i, f) => essayer(() => api.deposer(`/api/guides/${i}/fichier`, f), 'Fichier déposé.')
  const retirer = (i) => essayer(async () => { await api.del(`/api/guides/${i}`); aRetirer = null },
    'Guide retiré. Son livre ne quittera la liseuse qu\'après ton accord, dans « À traiter ».')
  const champ = 'h-10 rounded-lg border border-input bg-background px-3 outline-none focus:border-ring'
</script>

<ul class="mt-2 divide-y text-sm" aria-label="Guides">
  {#each guides as g (g.indice)}
    <li class="py-2">
      <div class="flex flex-wrap items-start justify-between gap-2">
        <span class="min-w-0">
          <span class="font-medium">{g.titre}</span>
          <span class="block text-muted-foreground">{g.editeur || 'éditeur manquant'}{g.date ? ` · ${g.date}` : ''}</span>
          {#if g.url}<a class="block break-all text-muted-foreground underline" href={g.url} target="_blank" rel="noopener">{g.url}</a>{/if}
          {#if g.manques.length}<span class="mt-0.5 flex items-center gap-1.5 font-medium"><TriangleAlert class="size-4" aria-hidden="true" />Il manque : {g.manques.join(', ')}</span>{/if}
        </span>
        <span class="flex flex-wrap items-center gap-1.5">
          {#if aRetirer === g.indice}
            <span>Retirer ce guide ?</span>
            <Button variant="outline" onclick={() => retirer(g.indice)} disabled={attente || lectureSeule}>Oui, retirer</Button>
            <Button variant="outline" onclick={() => (aRetirer = null)}>Non</Button>
          {:else}
            <Button variant="outline" onclick={() => (edition = { indice: g.indice, titre: g.titre, editeur: g.editeur, url: g.url, date: g.date, langue: g.langue })} disabled={lectureSeule}>Modifier la fiche</Button>
            <Button variant="outline" onclick={() => (aRetirer = g.indice)} disabled={lectureSeule}>Retirer…</Button>
          {/if}
        </span>
      </div>
      {#if !g.present}
        <label class="mt-2 flex flex-col gap-1">Déposer le fichier de ce guide{g.fichier ? ` (${g.fichier.split('.').pop().toUpperCase()} attendu)` : ''}
          <input type="file" accept=".pdf,.epub" disabled={attente || lectureSeule} onchange={(e) => e.currentTarget.files[0] && joindre(g.indice, e.currentTarget.files[0])}
                 class="block w-full rounded-lg border border-input bg-background p-2 file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-2 file:text-foreground" /></label>
      {/if}
      {#if edition?.indice === g.indice}{@render formulaire()}{/if}
    </li>
  {:else}<li class="py-2 text-muted-foreground">Aucun guide déclaré.</li>{/each}
</ul>
{#if edition?.indice === null}{@render formulaire()}
{:else}<div class="mt-2"><Button variant="outline" onclick={() => { edition = { indice: null, ...VIDE }; fichier = null }} disabled={lectureSeule}>Ajouter un guide</Button></div>{/if}
{#if attente}<p class="mt-2 text-sm text-muted-foreground">En cours…</p>{/if}
{#if message}<p class="mt-2 text-sm" role="status">{message}</p>{/if}

{#snippet formulaire()}
  <form class="mt-2 grid gap-2 rounded-xl bg-secondary p-3 text-sm md:grid-cols-2" onsubmit={(e) => { e.preventDefault(); enregistrer() }}>
    <label class="flex flex-col gap-1">Titre<input bind:value={edition.titre} required maxlength="200" class={champ} /></label>
    <label class="flex flex-col gap-1">Éditeur (qui publie ce guide)<input bind:value={edition.editeur} required maxlength="200" class={champ} /></label>
    <label class="flex flex-col gap-1 md:col-span-2">Adresse officielle (où il est publié)<input type="url" bind:value={edition.url} required maxlength="500" placeholder="https://" class={champ} /></label>
    <label class="flex flex-col gap-1">Date (facultative)<input bind:value={edition.date} maxlength="20" placeholder="2026-01" class={champ} /></label>
    <label class="flex flex-col gap-1">Langue<input bind:value={edition.langue} maxlength="10" class={champ} /></label>
    {#if edition.indice === null}
      <label class="flex flex-col gap-1 md:col-span-2">Fichier (PDF ou EPUB, 150 Mo au plus)
        <input type="file" accept=".pdf,.epub" required onchange={(e) => (fichier = e.currentTarget.files[0] || null)}
               class="block w-full rounded-lg border border-input bg-background p-2 file:mr-3 file:rounded-md file:border-0 file:bg-card file:px-3 file:py-2 file:text-foreground" /></label>
    {/if}
    <div class="flex flex-wrap gap-2 md:col-span-2">
      <Button type="submit" disabled={attente || (edition.indice === null && !fichier)}>Enregistrer</Button>
      <Button variant="outline" onclick={() => (edition = null)}>Annuler</Button>
    </div>
  </form>
{/snippet}
