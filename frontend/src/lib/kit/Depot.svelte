<script>
  // Zone de dépôt (2.1.1) : on y glisse des fichiers depuis l'explorateur, ou on les choisit.
  // Les fichiers d'un autre type que ceux attendus sont écartés ici, et le serveur recontrôle.
  import Upload from '@lucide/svelte/icons/upload'

  let { accepte = [], multiple = false, desactive = false, texte = 'Glisse un fichier ici', aide = '', onfichiers, nom = 'Déposer' } = $props()
  let survol = $state(false)
  let refus = $state('')
  let entree

  function recevoir(liste) {
    refus = ''
    let fichiers = [...liste]
    const bons = fichiers.filter((f) => accepte.some((e) => f.name.toLowerCase().endsWith(e)))
    if (bons.length < fichiers.length) refus = `${fichiers.length - bons.length} fichier(s) écarté(s) : seuls ${accepte.map((e) => e.slice(1).toUpperCase()).join(', ')} sont acceptés.`
    fichiers = multiple ? bons : bons.slice(0, 1)
    if (fichiers.length) onfichiers?.(fichiers)
    if (entree) entree.value = ''
  }
  function lacher(e) {
    e.preventDefault(); survol = false
    if (!desactive) recevoir(e.dataTransfer?.files || [])
  }
</script>

<div class="zone" class:survol class:desactive role="group" aria-label={nom}
     ondragenter={(e) => { e.preventDefault(); if (!desactive) survol = true }}
     ondragover={(e) => { e.preventDefault(); if (!desactive) survol = true }}
     ondragleave={() => (survol = false)} ondrop={lacher}>
  <Upload class="size-5 flex-none text-primary" aria-hidden="true" />
  <span class="texte">
    <span class="block font-medium">{survol ? 'Lâche ici' : texte}</span>
    {#if aide}<span class="block text-muted-foreground">{aide}</span>{/if}
  </span>
  <label class="choisir">
    ou choisir{multiple ? ' des fichiers' : ' un fichier'}
    <input bind:this={entree} type="file" {multiple} accept={accepte.join(',')} disabled={desactive} aria-label={nom}
           onchange={(e) => e.currentTarget.files.length && recevoir(e.currentTarget.files)} />
  </label>
</div>
{#if refus}<p class="mt-1 text-sm" role="status">{refus}</p>{/if}

<style>
  .zone { display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem; padding: 0.9rem 1rem; border-radius: 0.9rem;
    border: 1.5px dashed var(--input); background: var(--background); font-size: 0.875rem; transition: border-color 0.15s, background 0.15s; }
  .texte { flex: 1 1 12rem; min-width: 0; }
  .zone.survol { border-color: var(--app); border-style: solid; background: color-mix(in srgb, var(--app) 10%, var(--background)); }
  .zone.desactive { opacity: 0.55; }
  .choisir { position: relative; display: inline-flex; align-items: center; min-height: 2.75rem; padding: 0 0.9rem; border-radius: 0.6rem;
    border: 1px solid var(--input); font-weight: 500; cursor: pointer; }
  .choisir:focus-within { outline: 2px solid var(--ring); outline-offset: 2px; }
  .choisir input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
</style>
