<script>
  // « Connexion » : une tuile par service, avec son voyant. (pages/Connexion.svelte est la page du mot de passe.)
  import { onMount } from 'svelte'
  import TabletSmartphone from '@lucide/svelte/icons/tablet-smartphone'
  import BookUser from '@lucide/svelte/icons/book-user'
  import House from '@lucide/svelte/icons/house'
  import { api } from '$lib/api.js'
  import { quand } from '$lib/format.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let { lectureSeule = false, ondeconnecte } = $props()
  let d = $state(null)
  let choisi = $state(null)
  let message = $state('')
  let attente = $state('')
  let rapport = $state(null)
  let copie = $state(false)

  const refus = (e) => { if (e.statut === 401) ondeconnecte?.(); else message = e.message }
  async function lire() { try { d = await api.get('/api/connexions') } catch (e) { refus(e) } }
  async function verifier() {
    attente = 'verifier'; message = ''; rapport = null
    try { rapport = await api.post('/api/liseuse/verifier') } catch (e) { refus(e) }
    attente = ''
  }
  async function livrer() {
    attente = 'livrer'; message = ''
    try { await api.post('/api/livrer'); message = 'Livraison faite et vérifiée.'; rapport = null; await lire() } catch (e) { refus(e) }
    attente = ''
  }
  async function copier() {
    try { await navigator.clipboard.writeText(d.liseuse.cle_publique); copie = true } catch { copie = false }
  }
  const services = $derived(d ? [
    { cle: 'liseuse', nom: 'Liseuse', icone: TabletSmartphone, ok: d.liseuse.joignable,
      etat: !d.liseuse.reglee ? 'adresse non réglée' : d.liseuse.joignable ? 'répond' : 'ne répond pas' },
    { cle: 'carnet', nom: 'carnet', icone: BookUser, ok: d.carnet.present,
      etat: d.carnet.present ? `${d.carnet.nombre} contact(s) reçus` : 'aucun contact reçu' },
    { cle: 'ha', nom: 'Home Assistant', icone: House, ok: d.home_assistant.jeton_regle,
      etat: d.home_assistant.jeton_regle ? 'jeton réglé' : 'jeton absent' },
  ] : [])
  onMount(lire)
</script>

<header class="mb-5">
  <p class="etiquette">Kit d'urgence</p>
  <h1 class="titre">Connexion</h1>
</header>

{#if !d}
  <p class="text-sm text-muted-foreground">Lecture…</p>
{:else}
  <div class="grid grid-cols-2 gap-3 md:grid-cols-4" role="group" aria-label="Services">
    {#each services as s}
      {@const Icone = s.icone}
      <button type="button" aria-pressed={choisi === s.cle} onclick={() => { choisi = choisi === s.cle ? null : s.cle; message = '' }}
              class="flex min-h-28 flex-col gap-1 rounded-2xl border bg-card p-4 text-left transition-colors hover:border-primary aria-pressed:border-primary">
        <span class="flex items-start justify-between">
          <Icone class="size-6 text-primary" aria-hidden="true" />
          <span class="size-2.5 rounded-full {s.ok ? 'bg-valide' : 'bg-muted-foreground/40'}" aria-hidden="true"></span>
        </span>
        <span class="nom-tuile font-medium">{s.nom}</span>
        <span class="text-sm text-muted-foreground">{s.etat}</span>
      </button>
    {/each}
  </div>

  {#if choisi === 'liseuse'}
    <section class="mt-4 rounded-2xl border bg-card p-5" aria-label="Liseuse">
      <h2 class="text-lg font-semibold">Liseuse</h2>
      <p class="mt-1 text-sm text-muted-foreground">Le kit y écrit ses livres, dans le dossier <code>{d.liseuse.dossier}</code>, par le serveur SSH de KOReader. Il n'y lit que les empreintes de ses propres livres.</p>
      <dl class="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt class="text-muted-foreground">Adresse</dt><dd>{d.liseuse.adresse || 'non réglée'}</dd>
        <dt class="text-muted-foreground">Vue le</dt><dd>{quand(d.liseuse.vue_le)}</dd>
        <dt class="text-muted-foreground">Dernière livraison</dt><dd>{quand(d.liseuse.derniere_livraison)}</dd>
        <dt class="text-muted-foreground">Kit dessus</dt><dd>{d.liseuse.a_jour ? 'le même que sur le NAS' : 'plus ancien que celui du NAS'}</dd>
      </dl>
      <div class="mt-3 flex flex-wrap items-center gap-2">
        <Button variant="outline" onclick={verifier} disabled={!!attente}>{attente === 'verifier' ? 'Vérification…' : 'Vérifier'}</Button>
        <Button onclick={livrer} disabled={!!attente || lectureSeule}>{attente === 'livrer' ? 'Livraison…' : 'Livrer'}</Button>
      </div>
      <p class="mt-2 text-sm text-muted-foreground">« Vérifier » relit chaque livre sur la liseuse et le compare à celui du NAS, sans rien écrire. « Livrer » envoie ce qui diffère.</p>
      {#if rapport}
        <div class="mt-3 text-sm" role="status" id="rapport">
          <p>{rapport.identiques.length} livre(s) identiques{rapport.differents.length + rapport.absents.length ? '' : ' : la liseuse a bien le kit du NAS.'}</p>
          {#if rapport.differents.length}<p>Différents : {rapport.differents.join(', ')}</p>{/if}
          {#if rapport.absents.length}<p>Absents de la liseuse : {rapport.absents.join(', ')}</p>{/if}
          {#if rapport.en_trop.length}<p>Sur la liseuse mais plus dans le kit : {rapport.en_trop.join(', ')}</p>{/if}
        </div>
      {/if}
      <h3 class="etiquette mt-5">Clé à autoriser sur la liseuse</h3>
      <p class="mt-1 text-sm text-muted-foreground">À coller une fois dans <code>koreader/settings/SSH/authorized_keys</code>.</p>
      <pre class="mt-2 overflow-x-auto rounded-lg bg-secondary p-3 text-[0.78rem]">{d.liseuse.cle_publique}</pre>
      <div class="mt-2"><Button variant="outline" onclick={copier}>{copie ? 'Copiée' : 'Copier la clé'}</Button></div>
    </section>
  {:else if choisi === 'carnet'}
    <section class="mt-4 rounded-2xl border bg-card p-5" aria-label="carnet">
      <h2 class="text-lg font-semibold">carnet</h2>
      <p class="mt-1 text-sm text-muted-foreground">Le kit ne lit pas carnet et n'y écrit rien : c'est carnet qui dépose ici les contacts du groupe Urgence, puis demande une fabrication.</p>
      <dl class="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt class="text-muted-foreground">Contacts reçus</dt><dd>{d.carnet.nombre}</dd>
        <dt class="text-muted-foreground">Reçus le</dt><dd>{quand(d.carnet.recus_le)}</dd>
      </dl>
      <div class="mt-3 flex flex-wrap items-center gap-2">
        <Button variant="outline" onclick={lire}>Vérifier</Button>
        {#if d.carnet.url}<a class="text-sm underline" href={d.carnet.url} target="_blank" rel="noopener">Ouvrir carnet</a>{/if}
      </div>
    </section>
  {:else if choisi === 'ha'}
    <section class="mt-4 rounded-2xl border bg-card p-5" aria-label="Home Assistant">
      <h2 class="text-lg font-semibold">Home Assistant</h2>
      <p class="mt-1 text-sm text-muted-foreground">Il lit l'état du kit sans clé, et lance fabrication, livraison et « papier imprimé » avec un jeton. Le kit ne lui écrit rien.</p>
      <dl class="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt class="text-muted-foreground">Jeton</dt><dd>{d.home_assistant.jeton_regle ? 'réglé dans la stack' : 'absent : les boutons de Home Assistant sont refusés'}</dd>
        <dt class="text-muted-foreground">Dernier appel avec jeton</dt><dd>{quand(d.home_assistant.dernier_appel)}</dd>
        <dt class="text-muted-foreground">Adresses</dt><dd>{d.home_assistant.adresses.join(' · ')}</dd>
      </dl>
      <div class="mt-3"><Button variant="outline" onclick={lire}>Vérifier</Button></div>
    </section>
  {:else}
    <p class="mt-4 text-sm text-muted-foreground">Touche un service pour voir son état et ses gestes.</p>
  {/if}
  {#if message}<p class="mt-3 text-sm" role="status" id="message">{message}</p>{/if}
{/if}
