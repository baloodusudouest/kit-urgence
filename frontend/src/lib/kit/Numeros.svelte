<script>
  // Numéros publics du livre des contacts : ils n'existent nulle part ailleurs, ils se corrigent ici.
  import { api } from '$lib/api.js'
  import { jour } from '$lib/format.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let { numeros, lectureSeule = false, onchange, onerreur } = $props()
  let edition = $state(null)   // { cat, indice (null = ajout), nom, numero, note }
  let message = $state('')
  let attente = $state(false)

  async function essayer(faire, dit) {
    attente = true; message = ''
    try { await faire(); message = dit; edition = null; onchange?.() } catch (e) { if (e.statut === 401) onerreur?.(e); else message = e.message }
    attente = false
  }
  const enregistrer = () => {
    const corps = { nom: edition.nom, numero: edition.numero, note: edition.note }
    return essayer(() => edition.indice === null ? api.post(`/api/numeros/${edition.cat}`, corps) : api.put(`/api/numeros/${edition.cat}/${edition.indice}`, corps), 'Numéro enregistré.')
  }
  const verifie = (cat, i) => essayer(() => api.post(`/api/numeros/${cat}/${i}/verifie`), 'Noté : vérifié aujourd\'hui.')
  const supprimer = () => essayer(() => api.del(`/api/numeros/${edition.cat}/${edition.indice}`), 'Numéro supprimé.')
  const champ = 'h-10 rounded-lg border border-input bg-background px-3 outline-none focus:border-ring'
</script>

{#each numeros as cat (cat.indice)}
  <h3 class="etiquette mt-4">{cat.nom}</h3>
  <ul class="mt-1 divide-y" aria-label={cat.nom}>
    {#each cat.numeros as n (n.indice)}
      <li class="py-2">
        <div class="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
          <span class="min-w-0"><span class="font-medium">{n.nom}</span>
            {#if n.note}<span class="block text-muted-foreground">{n.note}</span>{/if}
            {#if n.verifie_le}<span class="block text-muted-foreground">vérifié le {jour(n.verifie_le)}</span>{/if}</span>
          <span class="flex flex-wrap items-center gap-2">
            <span class={n.a_completer ? 'font-medium' : ''}>{n.numero}</span>
            {#if n.a_verifier}<Button variant="outline" onclick={() => verifie(cat.indice, n.indice)} disabled={attente || lectureSeule}>Vérifié aujourd'hui</Button>{/if}
            <Button variant="outline" onclick={() => (edition = { cat: cat.indice, indice: n.indice, nom: n.nom, numero: n.a_completer ? '' : n.numero, note: n.note })} disabled={lectureSeule}>Modifier</Button>
          </span>
        </div>
        {#if edition && edition.cat === cat.indice && edition.indice === n.indice}{@render formulaire()}{/if}
      </li>
    {/each}
  </ul>
  {#if edition && edition.cat === cat.indice && edition.indice === null}{@render formulaire()}
  {:else}<div class="mt-1"><Button variant="outline" onclick={() => (edition = { cat: cat.indice, indice: null, nom: '', numero: '', note: '' })} disabled={lectureSeule}>Ajouter un numéro</Button></div>{/if}
{/each}
{#if message}<p class="mt-2 text-sm" role="status">{message}</p>{/if}

{#snippet formulaire()}
  <form class="mt-2 grid gap-2 rounded-xl bg-secondary p-3 md:grid-cols-3" onsubmit={(e) => { e.preventDefault(); enregistrer() }}>
    <label class="flex flex-col gap-1 text-sm">Nom<input bind:value={edition.nom} required maxlength="200" class={champ} /></label>
    <label class="flex flex-col gap-1 text-sm">Numéro<input bind:value={edition.numero} required maxlength="60" inputmode="tel" class={champ} /></label>
    <label class="flex flex-col gap-1 text-sm">Note (facultative)<input bind:value={edition.note} maxlength="300" class={champ} /></label>
    <div class="flex flex-wrap gap-2 md:col-span-3">
      <Button type="submit" disabled={attente}>Enregistrer</Button>
      <Button variant="outline" onclick={() => (edition = null)}>Annuler</Button>
      {#if edition.indice !== null}<Button variant="outline" class="ml-auto" onclick={supprimer} disabled={attente}>Supprimer ce numéro</Button>{/if}
    </div>
  </form>
{/snippet}
