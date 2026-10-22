#!/usr/bin/env bash
# AUTEUR : TEUGUIA TADJUIDJE Rodolf Séderis — Rihen
# =============================================================================
# construire_kits.sh — UNE chaîne de kits, dans un job du flux publier-kits.yml (Windows, Linux, macOS).
#
#   bash outils/construire_kits.sh <racine Nkentseu> <chaine> <sortie> <epreuves> <bibliotheques...>
#
# <chaine> = <systeme>-<architecture>-<variante>-<liaison> (ex. windows-x86_64-clang18-libcxx-statique).
# Pour chaque bibliothèque : la construire (Debug, Release ; ses dépendances viennent avec), en tirer le kit
# (scripts/MakeKit.py du moteur), puis l'ÉPROUVER comme un apprenant : un workspace qui charge le kit, un
# programme construit en Debug et en Release, LANCÉ seul (PATH réduit au système sous Windows). Les
# programmes : l'en-tête de la bibliothèque, plus ceux de <epreuves> qui la concernent (fils, police, sdf,
# pan, retours, reseau ; sans la bibliothèque standard).
#
# Sortie : <sortie>/kits/<Nom>-<chaine>.zip, <sortie>/kits/SHA256SUMS.txt et <sortie>/journaux/resume.md
# (| Nom | archive | épreuve Debug | épreuve Release |), que publier_kits.py lit : seul un kit « vert | vert »
# entre dans une publication.
#
# Environnement : PY (python ou python3), NK_ENABLE_VULKAN (0 pour les variantes sans Vulkan), VULKAN_SDK
# (variantes avec Vulkan), NK_TOOLCHAIN_ATTENDU (facultatif : la chaîne que Jenga DOIT avoir choisie seul,
# vérifiée dans chaque journal ; une autre rend la construction rouge, le nom de la chaîne mentirait),
# NK_TOOLCHAIN (facultatif, passé en `--toolchain` ; À ÉVITER avec Jenga 2.9.0 sous Linux et macOS : ses
# builders figent la famille du compilateur avant ce choix, essai 39758756603, gcc a reçu `-include-pch`).
# =============================================================================
set -u
RACINE=$(cd "${1:?racine Nkentseu}" && pwd)
CHAINE="${2:?chaine}"
SORTIE=$(mkdir -p "${3:?sortie}" && cd "$3" && pwd)
EPREUVES=$(cd "${4:?dossier des epreuves}" && pwd)
shift 4
LISTE="$*"
PY="${PY:-python3}"
# (bash 3.2 de macOS : ni tableau vide sous set -u, ni tableau associatif)
TC=""; [ -n "${NK_TOOLCHAIN:-}" ] && TC="--toolchain $NK_TOOLCHAIN"
chaine_tenue() { # chaine_tenue <journal> : 0 si Jenga y a pris NK_TOOLCHAIN_ATTENDU (ou si rien n'est attendu)
	[ -z "${NK_TOOLCHAIN_ATTENDU:-}" ] && return 0
	tr -d '\033' < "$1" | sed -E 's/\[[0-9;]*m//g' | grep -a -q -E "Toolchain:[[:space:]]+${NK_TOOLCHAIN_ATTENDU}([[:space:]]|\$)"
}
J="$SORTIE/journaux"
K="$SORTIE/kits"
TMP="$SORTIE/tmp"
mkdir -p "$J" "$K" "$TMP"
R="$J/resume.md"
printf '| Kit | Archive | Epreuve Debug | Epreuve Release |\n|---|---|---|---|\n' > "$R"

chemin() { # chemin lisible par Jenga (C:/... sous Windows)
	if command -v cygpath > /dev/null 2>&1; then cygpath -m "$1"; else printf '%s\n' "$1"; fi
}
borne() { # borne <secondes> <commande...> : timeout s'il existe, sinon perl (macOS n'a pas timeout)
	local s=$1; shift
	if command -v timeout > /dev/null 2>&1; then timeout "$s" "$@"; else perl -e 'alarm shift; exec @ARGV' "$s" "$@"; fi
}
systeme() { case "$CHAINE" in windows-*) echo Windows ;; linux-*) echo Linux ;; macos-*) echo macOS ;; esac; }

# Sous Windows, le programme se lance avec le PATH du SYSTÈME seulement (preuve que le kit n'exige aucune DLL
# du compilateur), plus le dossier de vulkan-1.dll pour une variante avec Vulkan (chez l'apprenant : son
# pilote graphique).
CHEMIN_LANCEMENT=""
if [ "$(systeme)" = Windows ]; then
	CHEMIN_LANCEMENT="/c/Windows/system32:/c/Windows"
	if [ "${NK_ENABLE_VULKAN:-}" != 0 ] && [ -n "${VULKAN_SDK:-}" ]; then
		VKDLL=$(find "$(cygpath -u "$VULKAN_SDK")" -iname vulkan-1.dll 2> /dev/null | head -1)
		[ -n "$VKDLL" ] && CHEMIN_LANCEMENT="$(dirname "$VKDLL"):$CHEMIN_LANCEMENT"
		echo "vulkan-1.dll pour les épreuves : ${VKDLL:-INTROUVABLE}"
	fi
fi

lancer() { # lancer <exe> : code de sortie du programme, borné à 60 s
	local exe=$1
	if [ "$(systeme)" = Windows ]; then
		(cd "$(dirname "$exe")" && env -i SYSTEMROOT='C:\Windows' WINDIR='C:\Windows' PATH="$CHEMIN_LANCEMENT" \
			/usr/bin/timeout 60 "./$(basename "$exe")")
	else
		(cd "$(dirname "$exe")" && borne 60 "./$(basename "$exe")")
	fi
}

eprouver() { # eprouver <Nom> <programme|-> <config> : 0 si construit et lancé avec le code 0
	local B=$1 prog=$2 C=$3
	local nom=${prog%.cpp}; [ "$prog" = - ] && nom=entete
	local W="$TMP/essais/${B}_${nom}"
	if [ "$C" = Debug ]; then
		rm -rf "$W"; mkdir -p "$W"
		if [ "$prog" = - ]; then
			local inc="$TMP/Kits/$B/include" h=""
			[ -f "$inc/$B/$B.h" ] && h="$B/$B.h"
			[ -z "$h" ] && h=$(cd "$inc" 2> /dev/null && find "$B" -maxdepth 1 -name '*.h' | sort | head -1)
			[ -z "$h" ] && h=$(cd "$inc" 2> /dev/null && find "$B" -name '*.h' | sort | head -1)
			printf '%s\n' "// épreuve du kit $B : son en-tête se compile chez l'apprenant, le kit se lie, le programme se lance" \
				"#include \"$h\"" "int main() { return 0; }" > "$W/main.cpp"
		else
			cp "$EPREUVES/$prog" "$W/main.cpp"
			cp "$EPREUVES/police.h" "$W/"
		fi
		local fn; fn="use$(echo "$B" | tr '[:upper:]' '[:lower:]')"
		printf '%s\n' 'from Jenga import *' "useconfig(\"$(chemin "$TMP/Kits/$B/$B.jenga")\")" '' 'with workspace("Essai"):' \
			'    RegisterJengaGlobalToolchains()' '    configurations(["Debug", "Release"])' \
			'    with project("App"):' '        consoleapp()' '        language("C++")' '        cppdialect("C++17")' \
			'        files(["main.cpp"])' "        $fn()" > "$W/Essai.jenga"
	fi
	(cd "$W" && "$PY" -m Jenga build --config "$C" --no-daemon $TC > "build_$C.log" 2>&1)
	if ! chaine_tenue "$W/build_$C.log"; then
		cp "$W/build_$C.log" "$J/essai_${B}_${nom}_$C.log"
		echo "   $B $nom $C : Jenga n'a pas pris la chaine ${NK_TOOLCHAIN_ATTENDU}" >&2
		return 1
	fi
	local exe; exe=$(find "$W/Build/Bin" -type f \( -name App -o -name App.exe \) 2> /dev/null | grep "/$C-" | head -1)
	if [ -z "$exe" ]; then
		cp "$W/build_$C.log" "$J/essai_${B}_${nom}_$C.log"
		echo "   $B $nom $C : PAS D'EXECUTABLE" >&2
		return 1
	fi
	local code sortie
	sortie=$(lancer "$exe" 2>&1 | tail -2 | tr '\n' ' ' | cut -c1-160)
	code=$(lancer "$exe" > /dev/null 2>&1; echo $?)
	echo "   $B $nom $C : code $code ; $sortie" >&2
	[ "$code" = 0 ]
}

programmes() { # les épreuves propres à une bibliothèque, d'après ce que son kit contient
	local B=$1 inc="$TMP/Kits/$1/include"
	case "$B" in
	NKNetwork) echo "retours.cpp reseau.cpp" ;;
	NKThreading) echo "fils.cpp" ;;
	NKFont) echo "police.cpp sdf.cpp" ;;
	NKAudio) echo "pan.cpp" ;;
	NKCanvas | NKRenderer) [ -d "$inc/NKFont" ] && echo "police.cpp" ;;
	esac
}

# 1. CONSTRUIRE chaque bibliothèque, Debug et Release
# ETAT_<Nom>_<config> : ok ou ECHEC
t0=$(date +%s)
for C in Debug Release; do
	for B in $LISTE; do
		L="$J/build_${B}_${C}.log"
		if (cd "$RACINE" && "$PY" -m Jenga build --target "$B" --config "$C" --no-daemon $TC > "$L" 2>&1) && chaine_tenue "$L"; then
			eval "ETAT_${B}_$C=ok"
			echo "$B $C : construit ($(grep -a -c 'warning:' "$L") avertissement(s))"
		else
			eval "ETAT_${B}_$C=ECHEC"
			echo "$B $C : ECHEC"
			grep -a -E 'error|undefined' "$L" | sort -u | head -5 || true
		fi
	done
done
echo "construction : $(( $(date +%s) - t0 )) s"

# 2. EXTRAIRE et ÉPROUVER chaque kit
verts=0
for B in $LISTE; do
	if [ "$(eval echo "\${ETAT_${B}_Debug:-}")" != ok ] || [ "$(eval echo "\${ETAT_${B}_Release:-}")" != ok ]; then
		echo "| $B | non construit | - | - |" >> "$R"; continue
	fi
	rm -rf "$TMP/Kits/$B" "$TMP/$B"-kit-*.zip
	if ! (cd "$RACINE" && "$PY" scripts/MakeKit.py --name "$B" --target "$B" --sortie "$(chemin "$TMP")" > "$J/makekit_$B.log" 2>&1); then
		echo "| $B | MakeKit en echec | - | - |" >> "$R"; continue
	fi
	Z=$(ls "$TMP/$B"-kit-*.zip 2> /dev/null | head -1)
	[ -z "$Z" ] && { echo "| $B | MakeKit sans archive | - | - |" >> "$R"; continue; }
	case "$CHAINE" in
	*-sansvulkan-*)
		# La variante SANS Vulkan ne doit plus lier vulkan-1. Quelles bibliothèques en ont une : la liste du job
		# preparer (celles dont le kit AVEC Vulkan lie vulkan-1, mesuré le 21/10 ; NKCanvas lie vulkan-1 sans
		# embarquer NKRHI, mesuré le 22/10 : « embarque NKRHI » n'est donc pas le critère).
		if grep -q -i 'vulkan-1' "$TMP/Kits/$B/$B.jenga" "$TMP/Kits/$B/KIT.txt"; then
			echo "| $B | ROUGE : la variante sans Vulkan lie encore vulkan-1 | - | - |" >> "$R"; continue
		fi ;;
	esac
	NOM="$B-$CHAINE.zip"
	cp "$Z" "$K/$NOM"
	EP=""
	for C in Debug Release; do
		rouges=""
		for P in - $(programmes "$B"); do
			n=${P%.cpp}; [ "$P" = - ] && n=entete
			eprouver "$B" "$P" "$C" || rouges="$rouges $n"
		done
		if [ -z "$rouges" ]; then EP="$EP | vert"; else EP="$EP | ROUGE ($(echo $rouges))"; fi
	done
	echo "| $B | $NOM$EP |" >> "$R"
	case "$EP" in " | vert | vert") verts=$((verts + 1)) ;; esac
	echo "$B : $NOM$EP"
done
(cd "$K" && for z in *.zip; do [ -f "$z" ] && printf '%s  %s\n' "$("$PY" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$z")" "$z"; done > SHA256SUMS.txt)
rm -rf "$TMP"
echo "kits verts : $verts sur $(echo $LISTE | wc -w)"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
	{ echo "### Kits $CHAINE : $verts vert(s) sur $(echo $LISTE | wc -w)"; echo; cat "$R"; } >> "$GITHUB_STEP_SUMMARY"
fi
[ "$verts" -gt 0 ]
