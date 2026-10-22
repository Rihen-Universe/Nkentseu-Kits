#!/usr/bin/env bash
# AUTEUR : TEUGUIA TADJUIDJE Rodolf Séderis — Rihen
# =============================================================================
# precedents.sh — télécharge, pour chaque bibliothèque, sa DERNIÈRE publication (la plus haute version
# <id>-v<x.y.z> publiée, jamais un brouillon) dans <dossier>/<id>-v<x.y.z>/ : manifeste.json, empreinte.json
# et ses archives. publier_kits.py --precedent <dossier> y compare les kits neufs (rien de changé : pas de
# publication ; le lot reprend alors l'archive déjà publiée).
#
#   GH_TOKEN=... bash outils/precedents.sh <dossier>      (dans un job : GITHUB_REPOSITORY est connu)
# =============================================================================
set -eu
D="${1:?dossier}"
mkdir -p "$D"
DEPOT="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY}"
gh release list --repo "$DEPOT" --limit 1000 --exclude-drafts --json tagName --jq '.[].tagName' \
	| grep -E '^[a-z0-9]+-v[0-9]+\.[0-9]+\.[0-9]+$' \
	| sed 's/-v/ /' | sort -k1,1 -k2,2V \
	| awk '{ derniere[$1] = $2 } END { for (i in derniere) print i "-v" derniere[i] }' | sort > "$D/.liste" || true
n=0
while read -r tag; do
	[ -n "$tag" ] || continue
	gh release download "$tag" --repo "$DEPOT" --dir "$D/$tag" --clobber
	test -f "$D/$tag/empreinte.json" || { echo "::error::$tag publiée sans empreinte.json : la comparaison est impossible"; exit 1; }
	n=$((n + 1))
done < "$D/.liste"
echo "publications précédentes : $n"
