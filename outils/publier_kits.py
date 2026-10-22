# AUTEUR : TEUGUIA TADJUIDJE Rodolf Séderis — Rihen
# =============================================================================
# publier_kits.py — PREPARE la publication VERSIONNEE des kits par bibliotheque publique (22/10/2026,
# tache 11 de moteur-retours). Ne publie RIEN : il range des fichiers dans un dossier ; c'est le coordinateur
# qui publie.
#
# Rodolf (22/10, relaye par la session du site) : un numero de version par kit, qui n'avance que quand CE kit
# change ; une page Nkentseu (Logiciels) qui liste tous les kits, a telecharger un par un ou ensemble. Schema
# final accorde avec la plateforme le 22/10 (MANDAT_moteur-retours.md, section 11), bibliotheques SEULEMENT.
#
# Ce qu'il fabrique, dans <sortie> :
#   <id>-v<version>/   (id = nom en minuscules) : les archives de la bibliotheque, renommees
#       <Nom>-<version>-<systeme>-<architecture>-<variante>-<liaison>.zip, son manifeste.json, son
#       empreinte.json (en-tetes et symboles exportes : ce que la fois suivante compare) et SHA256SUMS.txt ;
#   lot-kits-<date>/ : une archive groupee par systeme + architecture + variante + liaison (les archives des
#       bibliotheques, rangees telles quelles, sans recompression), son manifeste.json ("id":"kits") et
#       SHA256SUMS.txt.
# Une archive n'entre que si son epreuve est VERTE (resumes des constructions Windows et Linux ; resume.md
# des runs macOS).
#
# LA FOIS SUIVANTE (--precedent <dossier de la publication d'avant>) : chaque kit est compare a son dernier
# publie, archive par archive (meme systeme, architecture, variante, liaison) :
#   un en-tete ou un symbole exporte RETIRE  -> version MAJEURE (1.0.0 -> 2.0.0)
#   un en-tete ou un symbole exporte AJOUTE  -> version MINEURE (1.0.0 -> 1.1.0)
#   un autre contenu change (en-tete modifie, bibliotheque recompilee autrement) -> CORRECTIF (1.0.0 -> 1.0.1)
#   rien ne change                           -> PAS de nouvelle publication pour ce kit
# Un kit embarque ses dependances : un changement chez elles change donc aussi le kit.
#
#   py -3 -I publier_kits.py --moteur <SHA complet> [--precedent <dossier>]... [--sortie <dossier>] [--date AAAA-MM-JJ]
# (--precedent se repete : chaque publication passee ; la plus haute version de chaque kit l'emporte, et un kit
# inchange entre dans le lot par son archive deja publiee.)
# =============================================================================
import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

KITS21 = r'C:\Rihen\Livraisons\Kits_2026-10-21'
JOURNAUX = r'C:\Rihen\ateliers_kits\journaux'
# Les kits macOS du run 39730721448 : la copie du coordinateur si elle est la, sinon la mienne (gh run download)
MAC = next((d for d in (r'C:\Rihen\Livraisons\Kits_macos_2026-10-22', r'C:\Rihen\ateliers_kits\macos_39730721448')
            if os.path.isfile(os.path.join(d, 'kits-macos-arm64', 'journaux', 'resume.md'))), r'C:\Rihen\Livraisons\Kits_macos_2026-10-22')
NM_POSTE = r'D:\Rihen\Livraisons\NKCode_1.5.1\NKCode\tools\compilers\llvm-mingw\bin\llvm-nm.exe'


def trouver_nm():
    """llvm-nm (lit COFF, ELF et Mach-O) : NK_LLVM_NM, celui du paquet NKCode du poste, ou celui du PATH ou de
    /usr/lib/llvm-*. SANS lui, aucun symbole ne serait releve et la comparaison suivante croirait tous les
    symboles retires (version majeure a tort) : on s'arrete."""
    for c in (os.environ.get('NK_LLVM_NM', ''), NM_POSTE, shutil.which('llvm-nm') or ''):
        if c and os.path.isfile(c):
            return c
    for c in sorted(glob.glob('/usr/lib/llvm-*/bin/llvm-nm'), key=lambda p: int(re.sub(r'\D', '', p.split('/')[3]) or 0),
                    reverse=True):  # la plus recente
        return c
    raise SystemExit('llvm-nm introuvable (NK_LLVM_NM) : sans lui, les symboles exportes ne seraient pas releves')


NM = ''

BIBLIOTHEQUES = ('NKPlatform NKCore NKMemory NKContainers NKMath NKThreading NKLogger NKTime NKFileSystem NKStream '
                 'NKReflection NKSerialization NKNetwork NKConverse NKImage NKFont NKAudio NKMedia NKEvent NKWindow NKSL '
                 'NKRHI NKCanvas NKRenderer NKVFX NKECS NKUI NKGui NKCamera NKCollision NKPhysics NKAnima NKNavigation '
                 'NKXR').split()

# Une phrase par bibliotheque, d'apres l'en-tete ou le Readme de son module.
DESCRIPTIONS = {
    'NKPlatform': ("Détection de la plateforme, du compilateur et du processeur, et services du système d'exploitation.",
                   "Platform, compiler and CPU detection, and operating-system services."),
    'NKCore': ("Les types de base, macros, atomiques et utilitaires sur lesquels tout le moteur repose.",
               "The basic types, macros, atomics and utilities the whole engine rests on."),
    'NKMemory': ("Allocateurs (arène, pool, liste libre...) et pointeurs intelligents (NkSharedPtr, NkUniquePtr).",
                 "Allocators (arena, pool, free list...) and smart pointers (NkSharedPtr, NkUniquePtr)."),
    'NKContainers': ("Conteneurs fondamentaux (C++17) : tableaux, chaînes, tables, files, et le formatage NkFormat.",
                     "Fundamental containers (C++17): arrays, strings, maps, queues, and NkFormat formatting."),
    'NKMath': ("Le module mathématique : vecteurs, matrices, quaternions, fonctions et géométrie.",
               "The math module: vectors, matrices, quaternions, functions and geometry."),
    'NKThreading': ("Fils, verrous, variables de condition, futurs et promesses, réserve de fils.",
                    "Threads, locks, condition variables, futures and promises, thread pool."),
    'NKLogger': ("Journalisation à plusieurs sorties (console, fichiers, asynchrone), formatée par NkFormat.",
                 "Logging to several sinks (console, files, asynchronous), formatted with NkFormat."),
    'NKTime': ("Le temps : chronomètres, durées, horloges et dates.", "Time: stopwatches, durations, clocks and dates."),
    'NKFileSystem': ("Fichiers, dossiers et chemins, de la même façon sur chaque système.",
                     "Files, folders and paths, the same way on every system."),
    'NKStream': ("Flux de lecture et d'écriture : fichiers, console, binaire.", "Read and write streams: files, console, binary."),
    'NKReflection': ("Réflexion à l'exécution : classes, champs et méthodes décrits pour le moteur.",
                     "Runtime reflection: classes, fields and methods described for the engine."),
    'NKSerialization': ("Sérialisation : archives binaires, JSON et natives, avec versions de schéma.",
                        "Serialization: binary, JSON and native archives, with schema versioning."),
    'NKNetwork': ("Le réseau : sockets, HTTP, connexion fiable sur UDP, flux de bits, RPC, lobby, réplication.",
                  "Networking: sockets, HTTP, reliable connection over UDP, bit streams, RPC, lobby, replication."),
    'NKConverse': ("Parler à un modèle de langage : porter une invite vers un modèle et en rapporter la réponse, chez plusieurs fournisseurs.",
                   "Talking to a language model: carrying a prompt to a model and bringing back its reply, across several providers."),
    'NKImage': ("Images : lecture et écriture de nombreux formats (PNG, JPEG, BMP, GIF, HDR, EXR, WebP, SVG...).",
                "Images: reading and writing many formats (PNG, JPEG, BMP, GIF, HDR, EXR, WebP, SVG...)."),
    'NKFont': ("Polices : lecture des fichiers de police, atlas de glyphes, rendu SDF.",
               "Fonts: font file parsing, glyph atlases, SDF rendering."),
    'NKAudio': ("Le son : lecture, mixage et son dans l'espace, sans la bibliothèque standard.",
                "Audio: playback, mixing and spatial sound, without the standard library."),
    'NKMedia': ("Médias : reconnaît les conteneurs audio et vidéo (MP4, WebM, WAV, OGG, MP3, FLAC) et liste leurs pistes et codecs.",
                "Media: recognizes audio and video containers (MP4, WebM, WAV, OGG, MP3, FLAC) and lists their tracks and codecs."),
    'NKEvent': ("Les événements du moteur : clavier, souris, fenêtre, manettes, et leur distribution.",
                "Engine events: keyboard, mouse, window, gamepads, and their dispatch."),
    'NKWindow': ("Fenêtres et point d'entrée de l'application, sur chaque système.",
                 "Windows and the application entry point, on every system."),
    'NKSL': ("Nkentseu Shader Language : le langage de shaders du moteur, son compilateur et sa traduction vers chaque API.",
             "Nkentseu Shader Language: the engine's shader language, its compiler and its translation to each API."),
    'NKRHI': ("Interface matérielle de rendu (RHI) : un seul code pour OpenGL, Vulkan, DirectX 11 et 12, Metal.",
              "Rendering hardware interface (RHI): one code path for OpenGL, Vulkan, DirectX 11 and 12, Metal."),
    'NKCanvas': ("Le dessin 2D et l'application de rendu simple, sur le dorsal choisi au démarrage.",
                 "2D drawing and the simple rendering application, on the backend chosen at startup."),
    'NKRenderer': ("Le moteur de rendu 3D : matériaux, maillages, passes de rendu et shaders.",
                   "The 3D renderer: materials, meshes, render passes and shaders."),
    'NKVFX': ("Effets visuels posés sur NKRenderer : le producteur de maillage d'eau et le contrôle de vie des effets.",
              "Visual effects on top of NKRenderer: the water mesh producer and the effects liveness check."),
    'NKECS': ("Entités, composants et systèmes (ECS) : le monde d'un jeu ou d'une simulation.",
              "Entities, components and systems (ECS): the world of a game or a simulation."),
    'NKUI': ("Ancienne couche d'interface (remplacée par NKGui), gardée pour les projets existants.",
             "Former user-interface layer (replaced by NKGui), kept for existing projects."),
    'NKGui': ("La couche d'interface de Nkentseu : widgets, mise en page et thèmes.",
              "Nkentseu's user-interface layer: widgets, layout and themes."),
    'NKCamera': ("Caméras physiques : capture vidéo depuis les caméras de chaque système, une ou plusieurs à la fois.",
                 "Physical cameras: video capture from cameras on every system, one or several at a time."),
    'NKCollision': ("Détection de collisions 2D et 3D : formes, GJK, SAT, rayons, et monde de collision.",
                    "2D and 3D collision detection: shapes, GJK, SAT, rays, and a collision world."),
    'NKPhysics': ("Dynamique du corps rigide 2D et 3D, posée sur NKCollision.",
                  "2D and 3D rigid-body dynamics, built on NKCollision."),
    'NKAnima': ("Animation : clips, mélange, morphes, visage et mouvement.", "Animation: clips, blending, morph targets, face and motion."),
    'NKNavigation': ("Navigation : maillage de navigation (génération, requêtes) et recherche de chemin A*.",
                     "Navigation: navigation mesh (generation, queries) and A* pathfinding."),
    'NKXR': ("Réalité virtuelle et augmentée : casques, suivi et dorsaux XR.",
             "Virtual and augmented reality: headsets, tracking and XR backends."),
}

VARIANTES = {
    'clang18-libcxx': ("Compilateur du paquet NKCode (clang 18, libc++)", "NKCode's bundled compiler (clang 18, libc++)"),
    'clang18-libcxx-sansvulkan': ("Compilateur du paquet NKCode (clang 18, libc++), sans Vulkan",
                                  "NKCode's bundled compiler (clang 18, libc++), without Vulkan"),
    'msys2-libstdcxx': ("MSYS2 UCRT64 (clang, libstdc++)", "MSYS2 UCRT64 (clang, libstdc++)"),
    'msys2-libstdcxx-sansvulkan': ("MSYS2 UCRT64 (clang, libstdc++), sans Vulkan", "MSYS2 UCRT64 (clang, libstdc++), without Vulkan"),
    'gcc13-libstdcxx': ("GCC 13 (Ubuntu 24.04), libstdc++, sans Vulkan", "GCC 13 (Ubuntu 24.04), libstdc++, without Vulkan"),
    'clang18-libstdcxx': ("Clang 18 (Ubuntu 24.04), libstdc++, sans Vulkan", "Clang 18 (Ubuntu 24.04), libstdc++, without Vulkan"),
    'appleclang-libcxx': ("Apple Clang (Xcode), libc++, sans Vulkan (Metal et OpenGL)",
                          "Apple Clang (Xcode), libc++, without Vulkan (Metal and OpenGL)"),
}

# (cle, source, motif du nom source, systeme, architecture, variante, liaison, resume)
CHAINES = [
    ('llvm-avec', KITS21, '{B}-windows-x64-clang18-libcxx-statique.zip', 'windows', 'x86_64', 'clang18-libcxx', 'statique', 'tsv:llvm-avec'),
    ('llvm-sans', KITS21, '{B}-windows-x64-clang18-libcxx-statique-sansvulkan.zip', 'windows', 'x86_64', 'clang18-libcxx-sansvulkan',
     'statique', 'tsv:llvm-sans'),
    ('msys-avec', KITS21, '{B}-windows-x64-msys2-libstdcxx-statique.zip', 'windows', 'x86_64', 'msys2-libstdcxx', 'statique', 'tsv:msys-avec'),
    ('msys-sans', KITS21, '{B}-windows-x64-msys2-libstdcxx-statique-sansvulkan.zip', 'windows', 'x86_64', 'msys2-libstdcxx-sansvulkan',
     'statique', 'tsv:msys-sans'),
    # Ces archives portent « gcc13 » dans leur nom, mais clang 18.1.3 les a construites (mesuré le 22/10 : leurs
    # .a, KIT_COMPILER) : Jenga prend host-clang avant host-gcc, et WSL avait /usr/bin/clang. Publiees sous
    # leur vrai nom de chaine.
    ('linux', KITS21, '{B}-linux-x64-gcc13-libstdcxx-statique.zip', 'linux', 'x86_64', 'clang18-libstdcxx', 'statique', 'tsv:linux-gcc13'),
    ('mac-arm64', os.path.join(MAC, 'kits-macos-arm64', 'kits'), '{B}-kit-macos-arm64-appleclang-libcxx-statique.zip', 'macos', 'arm64',
     'appleclang-libcxx', 'statique', 'md:' + os.path.join(MAC, 'kits-macos-arm64', 'journaux', 'resume.md')),
    ('mac-x86_64', os.path.join(MAC, 'kits-macos-x86_64', 'kits'), '{B}-kit-macos-x86_64-appleclang-libcxx-statique.zip', 'macos', 'x86_64',
     'appleclang-libcxx', 'statique', 'md:' + os.path.join(MAC, 'kits-macos-x86_64', 'journaux', 'resume.md')),
]


def sha256(chemin):
    h = hashlib.sha256()
    with open(chemin, 'rb') as f:
        for bloc in iter(lambda: f.read(1 << 20), b''):
            h.update(bloc)
    return h.hexdigest()


def epreuves_vertes(resume):
    """Bibliotheques dont l'epreuve est verte pour une chaine : {nom: True}."""
    verts = {}
    genre, chemin = resume.split(':', 1)
    if genre == 'tsv':
        f = os.path.join(JOURNAUX, 'resume_%s.tsv' % chemin)
        if not os.path.isfile(f):
            return verts
        for l in open(f, encoding='utf-8').read().splitlines()[1:]:
            c = l.split('\t')
            if len(c) < 7:
                continue
            ok = c[3] == 'ok' and '/' in c[6] and c[6].split('/')[0] == c[6].split('/')[1] and c[6].split('/')[1] != '0'
            verts[c[0]] = ok  # la DERNIERE ligne d'une bibliotheque l'emporte (kits refaits le 22/10)
    else:
        if not os.path.isfile(chemin):
            return verts
        for l in open(chemin, encoding='utf-8', errors='replace').read().splitlines():
            m = re.match(r'\|\s*(NK\w+)\s*\|(.*)$', l)
            if m:
                cases = [x.strip() for x in m.group(2).split('|') if x.strip()]
                verts[m.group(1)] = len(cases) >= 3 and cases[1] == 'vert' and cases[2] == 'vert'
    return verts


def empreinte_contenu(b):
    """sha256 d'un fichier du kit ; pour une archive statique (.a, .lib : « !<arch> »), celui de ses MEMBRES
    (nom et donnees) sans leurs en-tetes : date, proprietaire et mode n'y entrent pas. L'`ar` d'Apple y ecrit
    l'heure de fabrication : sans cela, chaque reconstruction macOS publierait un correctif."""
    if not b.startswith(b'!<arch>\n'):
        return hashlib.sha256(b).hexdigest()
    h = hashlib.sha256(b'ar-membres\n')
    i = 8
    while i + 60 <= len(b):
        entete = b[i:i + 60]
        nom = entete[0:16].rstrip()
        try:
            taille = int(entete[48:58].strip() or b'0')
        except ValueError:
            return hashlib.sha256(b).hexdigest()  # pas une archive lisible : l'octet compte
        donnees = b[i + 60:i + 60 + taille]
        h.update(nom + b'\0' + str(taille).encode() + b'\0' + donnees)
        i += 60 + taille + (taille & 1)  # chaque membre est aligne sur 2 octets
    return h.hexdigest()


def lire_kit(zipf, nom):
    """KIT.txt, en-tetes (chemin -> sha256), vulkan, et la bibliotheque propre (Release) extraite pour llvm-nm."""
    with zipfile.ZipFile(zipf) as z:
        noms = z.namelist()
        kit_txt = next((n for n in noms if n.endswith('/KIT.txt')), None)
        texte = z.read(kit_txt).decode('utf-8', 'replace') if kit_txt else ''
        jenga = next((n for n in noms if n.endswith('/%s.jenga' % nom)), None)
        vulkan = 'vulkan-1' in texte.lower() or (bool(jenga) and 'vulkan-1' in z.read(jenga).decode('utf-8', 'replace').lower())
        # Le CONTENU, pas l'archive : un kit refait a l'identique change d'octets (dates du zip, « construit le »
        # de KIT.txt) sans changer de contenu ; comparer l'archive publierait un correctif a chaque fois.
        entetes, autres = {}, {}
        for n in noms:
            if n.endswith('/'):
                continue
            if '/include/' in n:
                entetes[n.split('/include/', 1)[1]] = hashlib.sha256(z.read(n)).hexdigest()
            else:
                b = z.read(n)
                if n == kit_txt or n == jenga:
                    # KIT.txt (« construit le ») et <Nom>.jenga (« Kit extrait ... le », KIT_BUILT) portent
                    # l'heure de fabrication : elle ne fait pas le contenu (mesuré le 22/10).
                    b = re.sub(rb'\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?', b'DATE', b)
                    autres[n.split('/', 1)[-1]] = hashlib.sha256(b).hexdigest()
                else:
                    autres[n.split('/', 1)[-1]] = empreinte_contenu(b)
        propre = [n for n in noms if re.search(r'/lib/Release-[^/]+/(lib)?%s\.(lib|a)$' % re.escape(nom), n)]
        symboles = []
        if propre:
            with tempfile.TemporaryDirectory() as d:
                p = os.path.join(d, os.path.basename(propre[0]))
                with open(p, 'wb') as f:
                    f.write(z.read(propre[0]))
                r = subprocess.run([NM, '--defined-only', '--extern-only', '--format=just-symbols', p], capture_output=True, text=True,
                                   encoding='utf-8', errors='replace')
                symboles = sorted(set(s.strip() for s in r.stdout.splitlines() if s.strip() and not s.endswith(':')))
    modules = []
    m = re.search(r'Modules, dans l\'ordre de lien[^\n]*\n((?:[ \t]+\S+\n)+)', texte)
    if m:
        modules = [x.strip() for x in m.group(1).splitlines() if x.strip()]
    return modules, vulkan, entetes, symboles, autres


def exige(systeme, architecture, variante, vulkan):
    if systeme == 'windows':
        if variante.startswith('clang18'):
            fr = "Windows 10 ou plus récent (x86_64) ; construire avec le compilateur du paquet NKCode (NKCode, ou tools\\jenga.cmd build)"
            en = "Windows 10 or newer (x86_64); build with NKCode's bundled compiler (NKCode, or tools\\jenga.cmd build)"
        else:
            fr = "Windows 10 ou plus récent (x86_64) ; construire avec MSYS2 UCRT64 (clang ou gcc, libstdc++)"
            en = "Windows 10 or newer (x86_64); build with MSYS2 UCRT64 (clang or gcc, libstdc++)"
        if vulkan:
            fr += " ; au démarrage, un pilote graphique Vulkan (vulkan-1.dll)"
            en += "; at startup, a Vulkan graphics driver (vulkan-1.dll)"
        return {'fr': fr, 'en': en}
    if systeme == 'linux':
        # Le kit EXIGE la famille de compilateur de ses archives (kitrequire de Jenga) : clang pour un kit clang.
        if variante.startswith('gcc'):
            cfr, cen = "gcc 13 ou plus récent (libstdc++)", "gcc 13 or newer (libstdc++)"
        else:
            cfr, cen = "clang 18 ou plus récent, avec libstdc++ (celui d'Ubuntu)", "clang 18 or newer, with libstdc++ (Ubuntu's)"
        return {'fr': "Linux x86_64, Ubuntu 24.04 ou plus récent (glibc 2.39) ; %s ; X11 et OpenGL" % cfr,
                'en': "Linux x86_64, Ubuntu 24.04 or newer (glibc 2.39); %s; X11 and OpenGL" % cen}
    return {'fr': "macOS 12 ou plus récent (%s) ; Xcode (Apple Clang, libc++)" % architecture,
            'en': "macOS 12 or newer (%s); Xcode (Apple Clang, libc++)" % architecture}


def version_suivante(v, niveau):
    a, b, c = (int(x) for x in v.split('.'))
    return {'majeure': '%d.0.0' % (a + 1), 'mineure': '%d.%d.0' % (a, b + 1), 'correctif': '%d.%d.%d' % (a, b, c + 1)}[niveau]


def comparer(avant, apres):
    """Niveau du changement entre deux empreintes d'une meme bibliotheque : None, correctif, mineure, majeure."""
    niveau = None
    rang = {None: 0, 'correctif': 1, 'mineure': 2, 'majeure': 3}
    for cle, e in apres.items():
        p = avant.get(cle)
        if p is None:
            n = 'mineure'  # une archive nouvelle (systeme, architecture ou variante de plus)
        else:
            ea, ep = set(p['entetes']), set(e['entetes'])
            sa, sp = set(p['symboles']), set(e['symboles'])
            if (ea - ep) or (sa - sp):
                n = 'majeure'
            elif (ep - ea) or (sp - sa):
                n = 'mineure'
            elif p.get('autres') != e['autres'] or any(p['entetes'][k] != e['entetes'][k] for k in ep):
                n = 'correctif'
            else:
                n = None
        if rang[n] > rang[niveau]:
            niveau = n
    for cle in avant:
        if cle not in apres:
            niveau = 'majeure'  # une archive retiree
    return niveau


def changements(avant, apres, v0):
    """Les nouveautes d'une version suivante, comptees (le coordinateur peut les reecrire avant de publier)."""
    n = {'eaj': set(), 'ere': set(), 'emo': set(), 'saj': 0, 'sre': 0, 'arch': 0}
    for cle, e in apres.items():
        p = avant.get(cle)
        if p is None:
            n['arch'] += 1
            continue
        n['eaj'] |= set(e['entetes']) - set(p['entetes'])
        n['ere'] |= set(p['entetes']) - set(e['entetes'])
        n['emo'] |= {k for k in set(e['entetes']) & set(p['entetes']) if e['entetes'][k] != p['entetes'][k]}
        n['saj'] = max(n['saj'], len(set(e['symboles']) - set(p['symboles'])))
        n['sre'] = max(n['sre'], len(set(p['symboles']) - set(e['symboles'])))
    fr, en = [], []
    for cle, f, g in (('ere', 'en-tête(s) retiré(s)', 'header(s) removed'), ('eaj', 'en-tête(s) ajouté(s)', 'header(s) added'),
                      ('emo', 'en-tête(s) modifié(s)', 'header(s) changed')):
        if n[cle]:
            fr.append('%d %s : %s.' % (len(n[cle]), f, ', '.join(sorted(n[cle])[:5]) + (' ...' if len(n[cle]) > 5 else '')))
            en.append('%d %s: %s.' % (len(n[cle]), g, ', '.join(sorted(n[cle])[:5]) + (' ...' if len(n[cle]) > 5 else '')))
    if n['sre'] or n['saj']:
        fr.append('Symboles exportés : %d retiré(s), %d ajouté(s).' % (n['sre'], n['saj']))
        en.append('Exported symbols: %d removed, %d added.' % (n['sre'], n['saj']))
    if n['arch']:
        fr.append('%d archive(s) nouvelle(s) (système, architecture ou compilateur).' % n['arch'])
        en.append('%d new archive(s) (system, architecture or compiler).' % n['arch'])
    retirees = [c for c in avant if c not in apres]
    if retirees:
        fr.append('Archive(s) retirée(s) : %s.' % ', '.join(retirees))
        en.append('Archive(s) removed: %s.' % ', '.join(retirees))
    if not fr:
        fr, en = ['Bibliothèque reconstruite (contenu changé, interface identique).'], ['Library rebuilt (content changed, same interface).']
    return {'fr': ['Depuis la %s : ' % v0 + fr[0]] + fr[1:], 'en': ['Since %s: ' % v0 + en[0]] + en[1:]}


def ecrire_sha(dossier):
    zips = sorted(f for f in os.listdir(dossier) if f.endswith('.zip'))
    with open(os.path.join(dossier, 'SHA256SUMS.txt'), 'w', encoding='utf-8', newline='\n') as s:
        for z in zips:
            s.write('%s  %s\n' % (sha256(os.path.join(dossier, z)), z))


def chaines_des_artefacts(racine):
    """Les chaines du flux : un sous-dossier kits-<systeme>-<architecture>-<variante>-<liaison> par artefact."""
    chaines = []
    for d in sorted(os.listdir(racine)):
        m = re.match(r'^kits-([a-z]+)-([a-z0-9_]+)-([a-z0-9-]+)-([a-z]+)$', d)
        if not m or not os.path.isdir(os.path.join(racine, d, 'kits')):
            continue
        chaine = d[len('kits-'):]
        chaines.append((chaine, os.path.join(racine, d, 'kits'), '{B}-%s.zip' % chaine, m.group(1), m.group(2), m.group(3), m.group(4),
                        'md:' + os.path.join(racine, d, 'journaux', 'resume.md')))
    return chaines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--moteur', required=True, help='SHA complet du superprojet construit')
    ap.add_argument('--date', default='2026-10-22')
    ap.add_argument('--sortie', default=r'C:\Rihen\Livraisons\Publication_kits_2026-10-22')
    # --precedent se repete : une publication ne range que les kits qui ont change, la derniere version d'un kit
    # peut donc etre dans une publication plus ancienne. La plus haute version de chaque kit l'emporte.
    ap.add_argument('--precedent', action='append', default=[], help='dossier d\'une publication precedente (se repete)')
    # --sources : le mode du flux publier-kits.yml (Nkentseu-Kits). Un sous-dossier kits-<chaine> par artefact
    # de construction, <chaine> = <systeme>-<architecture>-<variante>-<liaison>, avec kits/<Nom>-<chaine>.zip et
    # journaux/resume.md (| Nom | archive | epreuve Debug | epreuve Release |). Sans --sources : les kits du poste.
    ap.add_argument('--sources', default='', help='dossier des artefacts de construction (mode du flux)')
    a = ap.parse_args()
    os.makedirs(a.sortie, exist_ok=True)
    global NM, CHAINES
    NM = trouver_nm()
    if a.sources:
        CHAINES = chaines_des_artefacts(a.sources)
        if not CHAINES:
            raise SystemExit('aucun artefact kits-<chaine> dans %s' % a.sources)

    precedents = {}
    for racine in a.precedent:
        for d in os.listdir(racine):
            m = re.match(r'^([a-z0-9]+)-v(\d+\.\d+\.\d+)$', d)
            if m and os.path.isfile(os.path.join(racine, d, 'empreinte.json')):
                if m.group(1) in precedents and tuple(map(int, precedents[m.group(1)][0].split('.'))) >= tuple(map(int, m.group(2).split('.'))):
                    continue
                precedents[m.group(1)] = (m.group(2), json.load(open(os.path.join(racine, d, 'empreinte.json'), encoding='utf-8')),
                                          os.path.join(racine, d))

    verts = {c[0]: epreuves_vertes(c[7]) for c in CHAINES}
    publiees = {}
    manifestes = []
    groupes = {}
    ecartees = []
    for B in BIBLIOTHEQUES:
        ident = B.lower()
        fichiers, empreinte, deps = [], {}, set()
        sources = []
        for cle, src, motif, systeme, arch, variante, liaison, _ in CHAINES:
            z = os.path.join(src, motif.format(B=B))
            if not os.path.isfile(z):
                continue
            if not verts[cle].get(B, False):
                ecartees.append('%s %s : epreuve non verte' % (B, cle))
                continue
            modules, vulkan, entetes, symboles, autres = lire_kit(z, B)
            deps.update(m for m in modules if m in BIBLIOTHEQUES and m != B)
            k = '%s-%s-%s-%s' % (systeme, arch, variante, liaison)
            empreinte[k] = {'sha256': sha256(z), 'entetes': entetes, 'symboles': symboles, 'autres': autres}
            sources.append((z, systeme, arch, variante, liaison, vulkan))
        if not sources:
            ecartees.append('%s : aucune archive verte' % B)
            continue
        version = '1.0.0'
        nouveautes = {'fr': ['Première version numérotée.'], 'en': ['First numbered release.']}
        if ident in precedents:
            v0, e0, d0 = precedents[ident]
            niveau = comparer(e0, empreinte)
            if niveau is None:
                print('%-16s inchange depuis %s : pas de publication' % (B, v0))
                publiees[ident] = v0
                # Le lot, lui, contient tous les kits : celui-ci y entre par son archive deja publiee
                for x in json.load(open(os.path.join(d0, 'manifeste.json'), encoding='utf-8'))['fichiers']:
                    groupes.setdefault((x['systeme'], x['architecture'], x['variante']['id'], x['liaison']), []).append(os.path.join(d0, x['nom']))
                continue
            version = version_suivante(v0, niveau)
            nouveautes = changements(e0, empreinte, v0)
        dossier = os.path.join(a.sortie, '%s-v%s' % (ident, version))
        os.makedirs(dossier, exist_ok=True)
        for z, systeme, arch, variante, liaison, vulkan in sources:
            nom = '%s-%s-%s-%s-%s-%s.zip' % (B, version, systeme, arch, variante, liaison)
            dest = os.path.join(dossier, nom)
            shutil.copyfile(z, dest)
            v = VARIANTES.get(variante, (variante, variante))
            fichiers.append({'systeme': systeme, 'architecture': arch, 'liaison': liaison,
                             'variante': {'id': variante, 'fr': v[0], 'en': v[1]}, 'configurations': ['debug', 'release'],
                             'nom': nom, 'taille': os.path.getsize(dest), 'sha256': sha256(dest),
                             'exige': exige(systeme, arch, variante, vulkan)})
            groupes.setdefault((systeme, arch, variante, liaison), []).append(dest)
        manifeste = {'id': ident, 'genre': 'bibliotheque', 'nom': B, 'version': version, 'date': a.date, 'moteur': a.moteur,
                     'description': {'fr': DESCRIPTIONS[B][0], 'en': DESCRIPTIONS[B][1]},
                     'dependances': sorted(deps),  # remplace apres la boucle par {id: version}
                     'fichiers': fichiers, 'nouveautes': nouveautes}
        with open(os.path.join(dossier, 'empreinte.json'), 'w', encoding='utf-8', newline='\n') as f:
            json.dump(empreinte, f, ensure_ascii=False)
        ecrire_sha(dossier)
        publiees[ident] = version
        manifestes.append((dossier, manifeste))
        print('%-16s v%s : %d archive(s), %d dependance(s)' % (B, version, len(fichiers), len(deps)))

    # Les manifestes s'ecrivent APRES la boucle : la version d'une dependance est celle de CETTE publication, et
    # une dependance peut venir apres dans BIBLIOTHEQUES (NKCanvas embarque NKGui).
    for dossier, manifeste in manifestes:
        manifeste['dependances'] = {d.lower(): publiees.get(d.lower(), '1.0.0') for d in manifeste['dependances']}
        with open(os.path.join(dossier, 'manifeste.json'), 'w', encoding='utf-8', newline='\n') as f:
            json.dump(manifeste, f, ensure_ascii=False, indent=2)

    # Le lot : une archive groupee par systeme + architecture + variante + liaison. Rien de neuf : pas de lot.
    if not manifestes:
        for e in ecartees:
            print('ECARTE :', e)
        print('aucun kit n\'a change : rien a publier, pas de lot')
        return
    lot = os.path.join(a.sortie, 'lot-kits-%s' % a.date)
    os.makedirs(lot, exist_ok=True)
    liste = []
    for (systeme, arch, variante, liaison), membres in sorted(groupes.items()):
        nom = 'Nkentseu-kits-%s-%s-%s-%s-%s.zip' % (a.date, systeme, arch, variante, liaison)
        dest = os.path.join(lot, nom)
        with zipfile.ZipFile(dest, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
            for m in sorted(membres):
                zf.write(m, os.path.basename(m))
        taille = os.path.getsize(dest)
        if taille >= 2 * 1024 ** 3:
            raise SystemExit('archive groupee trop grosse (>= 2 Gio) : %s' % nom)
        v = VARIANTES.get(variante, (variante, variante))
        liste.append({'systeme': systeme, 'architecture': arch, 'liaison': liaison, 'variante': {'id': variante, 'fr': v[0], 'en': v[1]},
                      'nom': nom, 'taille': taille, 'sha256': sha256(dest)})
        print('lot %-60s %d archives, %.0f Mo' % (nom, len(membres), taille / 1e6))
    with open(os.path.join(lot, 'manifeste.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'id': 'kits', 'genre': 'lot', 'nom': 'Kits Nkentseu', 'version': a.date, 'date': a.date, 'moteur': a.moteur,
                   'description': {'fr': "Tous les kits des bibliothèques publiques de Nkentseu, groupés par système, architecture, compilateur et liaison.",
                                   'en': "All Nkentseu public-library kits, grouped by system, architecture, compiler and linkage."},
                   'bibliotheques': dict(sorted(publiees.items())), 'groupes': liste}, f, ensure_ascii=False, indent=2)
    ecrire_sha(lot)
    for e in ecartees:
        print('ECARTE :', e)
    print('%d bibliotheque(s) ; lot : %d archive(s) groupee(s)' % (len(publiees), len(liste)))


if __name__ == '__main__':
    main()
