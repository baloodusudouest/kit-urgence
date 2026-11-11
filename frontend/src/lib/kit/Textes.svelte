<script>
  // Les textes d'un livre (00 ou 01) : on en ouvre un, on l'écrit, on enregistre.
  // Enregistrer garde l'ancienne version (les dix dernières) et ne fabrique rien : le kit passe « à refabriquer ».
  import { api } from '$lib/api.js'
  import { quand } from '$lib/format.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let { livre, textes, lectureSeule = false, onchange, onerreur, ouvrir = null } = $props()
  let t = $state(null)          // texte ouvert : { nom, contenu, versions }
  let brouillon = $state('')
  let vue = $state(null)        // ancienne version regardée : { id, contenu }
  let message = $state('')
  let attente = $state(false)
  let aSupprimer = $state(false)
  let nouveau = $state({ titre: '', numero: 60 })

  const change = $derived(t !== null && brouillon !== t.contenu)

  async function essayer(faire) {
    attente = true; message = ''
    try { await faire() } catch (e) { if (e.statut === 401) onerreur?.(e); else message = e.message }
    attente = false
  }
  async function ouvrirTexte(nom) {
    if (t?.nom === nom) { t = null; return }
    await essayer(async () => { t = await api.get('/api/textes/' + encodeURIComponent(nom)); brouillon = t.contenu; vue = null; aSupprimer = false })
  }
  const enregistrer = () => essayer(async () => {
    t = await api.put('/api/textes/' + encodeURIComponent(t.nom), { contenu: brouillon })
    brouillon = t.contenu; message = 'Enregistré. Le livre sera refait à la prochaine fabrication.'; onchange?.()
  })
  const voir = (id) => essayer(async () => {
    vue = vue?.id === id ? null : await api.get(`/api/textes/${encodeURIComponent(t.nom)}/versions/${id}`)
  })
  const revenir = (id) => essayer(async () => {
    t = await api.post(`/api/textes/${encodeURIComponent(t.nom)}/revenir`, { version: id })
    brouillon = t.contenu; vue = null; message = 'Ancienne version remise. Celle que tu quittes reste dans la liste.'; onchange?.()
  })
  const supprimer = () => essayer(async () => {
    await api.del('/api/textes/' + encodeURIComponent(t.nom)); t = null; message = 'Texte supprimé (gardé dans les versions du NAS).'; onchange?.()
  })
  const creer = () => essayer(async () => {
    const r = await api.post('/api/textes', { titre: nouveau.titre, numero: Number(nouveau.numero) })
    nouveau = { titre: '', numero: 60 }; onchange?.(); await ouvrirTexte(r.nom)
  })
  // Venu d'un lien de « À traiter » : le texte demandé s'ouvre, une seule fois
  import { onMount } from 'svelte'
  onMount(() => { if (ouvrir && textes.some((x) => x.nom === ouvrir)) ouvrirTexte(ouvrir) })
</script>

<ul class="mt-3 divide-y" aria-label="Textes">
  {#each textes.filter((x) => x.livre === livre) as x (x.nom)}
    <li class="py-2">
      <button type="button" class="flex min-h-11 w-full items-center justify-between gap-3 text-left" aria-expanded={t?.nom === x.nom} onclick={() => ouvrirTexte(x.nom)}>
        <span class="font-medium">{x.titre}</span>
        <span class="flex-none text-muted-foreground">{x.a_completer ? `${x.a_completer} à compléter` : `${x.mots} mots`}</span>
      </button>
      {#if t?.nom === x.nom}
        <div class="mt-2">
          <label class="etiquette" for={'texte-' + x.nom}>Texte (Markdown : « # » pour un titre, « - » pour une liste)</label>
          <textarea id={'texte-' + x.nom} bind:value={brouillon} rows="16" spellcheck="true" disabled={lectureSeule}
                    class="mt-1 block w-full rounded-lg border border-input bg-background p-3 font-mono text-[0.85rem] leading-relaxed outline-none focus:border-ring"></textarea>
          <div class="mt-2 flex flex-wrap items-center gap-2">
            <Button onclick={enregistrer} disabled={attente || !change || lectureSeule}>Enregistrer</Button>
            {#if change}<Button variant="outline" onclick={() => (brouillon = t.contenu)}>Abandonner mes changements</Button>{/if}
            {#if livre !== '00'}
              {#if aSupprimer}
                <span class="text-sm">Supprimer ce texte du livre ?</span>
                <Button variant="outline" onclick={supprimer} disabled={attente || lectureSeule}>Oui, supprimer</Button>
                <Button variant="outline" onclick={() => (aSupprimer = false)}>Non</Button>
              {:else}
                <Button variant="outline" class="ml-auto" onclick={() => (aSupprimer = true)} disabled={lectureSeule}>Supprimer…</Button>
              {/if}
            {/if}
          </div>
          {#if t.versions.length}
            <h4 class="etiquette mt-4">Versions gardées ({t.versions.length} sur 10 au plus)</h4>
            <ul class="mt-1 divide-y" aria-label="Versions">
              {#each t.versions as v (v.id)}
                <li class="py-1.5">
                  <span class="flex flex-wrap items-center justify-between gap-2">
                    <span>{quand(v.le)} <span class="text-muted-foreground">· {v.mots} mots</span></span>
                    <span class="flex gap-2">
                      <Button variant="outline" onclick={() => voir(v.id)}>{vue?.id === v.id ? 'Fermer' : 'Voir'}</Button>
                      <Button variant="outline" onclick={() => revenir(v.id)} disabled={attente || lectureSeule}>Revenir à cette version</Button>
                    </span>
                  </span>
                  {#if vue?.id === v.id}<pre class="mt-2 max-h-72 overflow-auto rounded-lg bg-secondary p-3 text-[0.82rem] whitespace-pre-wrap">{vue.contenu}</pre>{/if}
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      {/if}
    </li>
  {/each}
</ul>
{#if message}<p class="mt-2 text-sm" role="status">{message}</p>{/if}

{#if livre === '01'}
  <form class="mt-4 flex flex-wrap items-end gap-2 border-t pt-4" onsubmit={(e) => { e.preventDefault(); creer() }}>
    <label class="flex min-w-40 flex-1 flex-col gap-1 text-sm">Nouveau texte : son titre
      <input bind:value={nouveau.titre} required maxlength="60" class="h-10 rounded-lg border border-input bg-background px-3 outline-none focus:border-ring" /></label>
    <label class="flex w-28 flex-col gap-1 text-sm">Place (1 à 99)
      <input type="number" min="1" max="99" bind:value={nouveau.numero} required class="h-10 rounded-lg border border-input bg-background px-3 outline-none focus:border-ring" /></label>
    <Button type="submit" variant="outline" disabled={attente || lectureSeule}>Créer</Button>
  </form>
  <p class="mt-1 text-sm text-muted-foreground">La place range les textes dans le livre : 10 électricité, 20 eau, 30 chauffage…</p>
{/if}
