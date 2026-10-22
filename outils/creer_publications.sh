#!/usr/bin/env bash
# AUTEUR : TEUGUIA TADJUIDJE Rodolf Séderis — Rihen
# =============================================================================
# creer_publications.sh — crée les publications GitHub de ce dépôt d'après le dossier que publier_kits.py a
# rangé : une par bibliothèque qui a changé (<id>-v<version> : ses archives, manifeste.json, empreinte.json,
# SHA256SUMS.txt) et le lot (kits-AAAA-MM-JJ : les archives groupées, manifeste.json, SHA256SUMS.txt).
#
#   GH_TOKEN=... bash outils/creer_publications.sh <dossier> <essai : true|false>
#
# ESSAI (true) : des BROUILLONS seulement, nommés essai-<run>-<étiquette> (rien n'est publié, aucune
# étiquette n'est créée ; precedents.sh ne lit jamais un brouillon). Sinon : de vraies publications.
# Une étiquette déjà publiée arrête tout : on ne remplace jamais une publication.
# =============================================================================
set -eu
D="${1:?dossier}"
ESSAI="${2:?essai true ou false}"
DEPOT="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY}"
CIBLE="${GITHUB_SHA:?GITHUB_SHA}"
PREFIXE=""
OPTION=""
if [ "$ESSAI" = true ]; then
	PREFIXE="essai-${GITHUB_RUN_ID:?GITHUB_RUN_ID}-"
	OPTION="--draft"
fi

notes() { # notes <manifeste.json> <fichier> : description et nouveautés, en français puis en anglais
	python3 - "$1" > "$2" << 'FIN'
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
m = json.load(open(sys.argv[1], encoding='utf-8'))
print(m['description']['fr'])
print()
if m.get('genre') == 'lot':
    print('Bibliothèques : ' + ', '.join('%s %s' % (k, v) for k, v in sorted(m['bibliotheques'].items())))
else:
    print('## Nouveautés')
    for l in m['nouveautes']['fr']:
        print('- ' + l)
    print()
    print('Contient : ' + (', '.join('%s %s' % (k, v) for k, v in sorted(m['dependances'].items())) or 'rien d\'autre'))
print()
print('---')
print()
print(m['description']['en'])
print()
if m.get('genre') != 'lot':
    print("## What's new")
    for l in m['nouveautes']['en']:
        print('- ' + l)
print()
print('Moteur / engine : Rihen-Universe/Nkentseu@' + m['moteur'])
FIN
}

publier() { # publier <dossier> <étiquette> <titre>
	local d=$1 tag="$PREFIXE$2" titre=$3
	if gh release view "$tag" --repo "$DEPOT" > /dev/null 2>&1; then
		echo "::error::la publication $tag existe déjà : rien n'est remplacé"
		exit 1
	fi
	notes "$d/manifeste.json" "$RUNNER_TEMP/notes.md"
	# shellcheck disable=SC2086
	gh release create "$tag" --repo "$DEPOT" --target "$CIBLE" --title "$titre" --notes-file "$RUNNER_TEMP/notes.md" $OPTION \
		"$d"/*.zip "$d/manifeste.json" "$d/SHA256SUMS.txt" $( [ -f "$d/empreinte.json" ] && echo "$d/empreinte.json" )
	echo "$tag : $(ls "$d"/*.zip | wc -l) archive(s)${OPTION:+ (brouillon)}"
}

n=0
for d in "$D"/*-v*/; do
	[ -d "$d" ] || continue
	d=${d%/}
	b=$(basename "$d")
	titre=$(python3 -c 'import json,sys; m=json.load(open(sys.argv[1],encoding="utf-8")); print(m["nom"]+" "+m["version"])' "$d/manifeste.json")
	publier "$d" "$b" "$titre"
	n=$((n + 1))
done
for d in "$D"/lot-kits-*/; do
	[ -d "$d" ] || continue
	d=${d%/}
	date=${d##*/lot-kits-}
	publier "$d" "kits-$date" "Kits Nkentseu $date"
done
echo "bibliothèques publiées${OPTION:+ en brouillon} : $n"
