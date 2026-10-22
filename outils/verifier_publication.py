# AUTEUR : TEUGUIA TADJUIDJE Rodolf Séderis — Rihen
# =============================================================================
# verifier_publication.py — contrôle, AVANT toute publication, le dossier rangé par publier_kits.py, par un
# chemin à lui (il ne réemploie aucune fonction du script qu'il contrôle) :
#   - chaque <id>-v<version>/ : le manifeste a les clés du schéma, chaque archive existe avec sa taille et son
#     sha256 (hexa minuscule), son nom suit <Nom>-<version>-<systeme>-<architecture>-<variante>-<liaison>.zip,
#     SHA256SUMS.txt est juste et complet, aucune archive hors manifeste ;
#   - chaque archive est, à l'octet près, un kit d'artefact dont l'épreuve est « vert | vert » dans le
#     resume.md de son artefact (lu ici, ligne à ligne) ;
#   - le lot : chaque archive groupée a sa taille, son sha256, moins de 2 Gio, et contient exactement les
#     archives de son groupe.
# Code 0 si tout est juste ; sinon la liste des fautes et 1.
#
#   python3 outils/verifier_publication.py <publication> <sources> [<precedents>]
# =============================================================================
import hashlib
import json
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLES = {'id', 'genre', 'nom', 'version', 'date', 'moteur', 'description', 'dependances', 'fichiers', 'nouveautes'}
CLES_FICHIER = {'systeme', 'architecture', 'liaison', 'variante', 'configurations', 'nom', 'taille', 'sha256', 'exige'}


def empreinte(chemin):
    h = hashlib.sha256()
    with open(chemin, 'rb') as f:
        for bloc in iter(lambda: f.read(1 << 20), b''):
            h.update(bloc)
    return h.hexdigest()


def kits_verts(sources):
    """{sha256 : (chaine, nom)} des kits d'artefact dont l'épreuve est verte en Debug ET en Release."""
    verts = {}
    for d in sorted(os.listdir(sources)):
        r = os.path.join(sources, d, 'journaux', 'resume.md')
        if not d.startswith('kits-') or not os.path.isfile(r):
            continue
        for ligne in open(r, encoding='utf-8', errors='replace').read().splitlines():
            c = [x.strip() for x in ligne.strip().strip('|').split('|')]
            if len(c) == 4 and c[0].startswith('NK') and c[2] == 'vert' and c[3] == 'vert':
                z = os.path.join(sources, d, 'kits', c[1])
                if os.path.isfile(z):
                    verts[empreinte(z)] = (d[len('kits-'):], c[1])
    return verts


def main():
    pub, sources = sys.argv[1], sys.argv[2]
    precedents = sys.argv[3] if len(sys.argv) > 3 else ''
    verts = kits_verts(sources)
    fautes = []
    groupes = {}
    n = 0
    for d in sorted(os.listdir(pub)):
        dossier = os.path.join(pub, d)
        m = re.match(r'^([a-z0-9]+)-v(\d+\.\d+\.\d+)$', d)
        if not m or not os.path.isdir(dossier):
            continue
        man = json.load(open(os.path.join(dossier, 'manifeste.json'), encoding='utf-8'))
        if set(man) != CLES or man['id'] != m.group(1) or man['version'] != m.group(2) or man['genre'] != 'bibliotheque':
            fautes.append('%s : manifeste hors schéma' % d)
            continue
        noms = set()
        for f in man['fichiers']:
            if set(f) != CLES_FICHIER:
                fautes.append('%s : fichier hors schéma' % d)
                continue
            p = os.path.join(dossier, f['nom'])
            voulu = '%s-%s-%s-%s-%s-%s.zip' % (man['nom'], man['version'], f['systeme'], f['architecture'], f['variante']['id'],
                                                f['liaison'])
            if f['nom'] != voulu or not os.path.isfile(p):
                fautes.append('%s : %s absent ou mal nommé' % (d, f['nom']))
                continue
            s = empreinte(p)
            if os.path.getsize(p) != f['taille'] or s != f['sha256'] or not re.match(r'^[0-9a-f]{64}$', f['sha256']):
                fautes.append('%s : taille ou sha256 faux pour %s' % (d, f['nom']))
            chaine = '%s-%s-%s-%s' % (f['systeme'], f['architecture'], f['variante']['id'], f['liaison'])
            if verts.get(s, ('', ''))[0] != chaine:
                fautes.append('%s : %s n\'est pas un kit vert de l\'artefact kits-%s' % (d, f['nom'], chaine))
            noms.add(f['nom'])
            groupes.setdefault(chaine, {})[f['nom']] = s
            n += 1
        zips = {x for x in os.listdir(dossier) if x.endswith('.zip')}
        if zips != noms:
            fautes.append('%s : archives hors manifeste %s' % (d, sorted(zips ^ noms)))
        lignes = sorted(l for l in open(os.path.join(dossier, 'SHA256SUMS.txt'), encoding='utf-8').read().splitlines() if l)
        if lignes != sorted('%s  %s' % (empreinte(os.path.join(dossier, z)), z) for z in zips):
            fautes.append('%s : SHA256SUMS.txt faux' % d)
    # Les kits inchangés entrent dans le lot par leur archive déjà publiée
    if precedents and os.path.isdir(precedents):
        for d in sorted(os.listdir(precedents)):
            mp = os.path.join(precedents, d, 'manifeste.json')
            if os.path.isfile(mp) and not os.path.isdir(os.path.join(pub, d)):
                man = json.load(open(mp, encoding='utf-8'))
                for f in man['fichiers']:
                    chaine = '%s-%s-%s-%s' % (f['systeme'], f['architecture'], f['variante']['id'], f['liaison'])
                    groupes.setdefault(chaine, {}).setdefault(f['nom'], f['sha256'])
    lots = [x for x in os.listdir(pub) if x.startswith('lot-kits-')]
    for x in lots:
        lot = os.path.join(pub, x)
        man = json.load(open(os.path.join(lot, 'manifeste.json'), encoding='utf-8'))
        for g in man['groupes']:
            p = os.path.join(lot, g['nom'])
            chaine = '%s-%s-%s-%s' % (g['systeme'], g['architecture'], g['variante']['id'], g['liaison'])
            if not os.path.isfile(p) or os.path.getsize(p) != g['taille'] or empreinte(p) != g['sha256'] or g['taille'] >= 2 * 1024 ** 3:
                fautes.append('lot : %s absent, taille, sha256 ou 2 Gio' % g['nom'])
                continue
            with zipfile.ZipFile(p) as z:
                dedans = {i.filename: hashlib.sha256(z.read(i)).hexdigest() for i in z.infolist()}
            if dedans != groupes.get(chaine, {}):
                fautes.append('lot : %s ne contient pas exactement les archives de son groupe' % g['nom'])
    print('vérification : %d archive(s) de bibliothèque, %d lot(s), %d kit(s) vert(s) dans les artefacts ; fautes : %d'
          % (n, len(lots), len(verts), len(fautes)))
    for f in fautes:
        print('FAUTE', f)
    sys.exit(1 if fautes else 0)


if __name__ == '__main__':
    main()
