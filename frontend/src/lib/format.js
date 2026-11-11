// Dates et poids, dits simplement.
export function quand(iso) {
  if (!iso) return 'jamais'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'jamais'
  return d.toLocaleString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function jour(iso) {
  if (!iso) return 'jamais'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? 'jamais' : d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
}

export function poids(octets) {
  if (!octets) return '—'
  if (octets < 1024 * 1024) return `${Math.max(1, Math.round(octets / 1024))} ko`
  return `${(octets / 1024 / 1024).toFixed(1).replace('.', ',')} Mo`
}

export const lienLivre = (nom) => '/api/livres/fichier?nom=' + encodeURIComponent(nom)
