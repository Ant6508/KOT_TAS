"""Ce que la seance affiche.

Formatage pur : ces fonctions rendent des chaines et ne savent pas ou elles
vont. Seule `ecrire_en_place` touche a un flux, et on lui passe lequel.
"""

from __future__ import annotations

import sys

from controller.trace import Etat

# Assez large pour la ligne d'etat complete. Sert a effacer ce qui precede
# quand la nouvelle ligne est plus courte que l'ancienne.
LARGEUR_LIGNE = 100


def ligne_etat(
    image: int,
    etat: Etat | None,
    sauts: int,
    en_pause: bool,
    turbo: bool = False,
) -> str:
    """La ligne reecrite en place a chaque avance.

    `etat` vaut None tant qu'aucune image n'a ete enregistree : on le dit,
    plutot que d'afficher des zeros qui passeraient pour des mesures.
    """
    if etat is None:
        mesures = "aucune image enregistree"
    else:
        mesures = (
            f"x={etat.x:10.4f} y={etat.y:10.4f} "
            f"vx={etat.vx:8.4f} vy={etat.vy:8.4f}"
        )
    mode = "PAUSE" if en_pause else "MARCHE"
    if turbo:
        mode += "+TURBO"
    return f"image {image:5d} | {mesures} | {sauts} saut(s) | {mode}"


def ligne_saut(image: int, decollage: int) -> str:
    """Les deux images, toujours, pour qu'aucune convention ne reste implicite.

    Le film date le tap a l'image ou il est EMIS ; le heros decolle deux pas
    plus tard (NOTES.md, jalon 5, section 5).
    """
    return (
        f"saut pose a l'image {image} -> decollage attendu a l'image {decollage}"
    )


def ligne_sauts(sauts: list[int], index: int | None) -> str:
    """La liste des sauts du film, celui qu'on travaille entre crochets."""
    if not sauts:
        return "sauts  aucun -- Espace en pose un a l'image courante"
    marques = [
        f"[{image}]" if rang == index else f"{image}"
        for rang, image in enumerate(sauts)
    ]
    return "sauts  " + "  ".join(marques)


def ligne_decalage(rang: int, avant: int, apres: int, decollage: int) -> str:
    """Le mouvement d'un saut, avec l'image du decollage qui en decoule.

    `rang` est compte a partir de 1 : c'est un numero pour l'operateur, pas un
    indice de liste.
    """
    return (
        f"saut {rang} : {avant} -> {apres} "
        f"(decollage attendu a l'image {decollage})"
    )


def ligne_issue(statut: str, image: int | None) -> str:
    if statut == "death":
        return f"le heros a disparu a l'image {image} : le run s'arrete la"
    return "run incomplet : le heros est toujours la"


def ligne_cible(cible) -> str:
    """La cible en clair, avec le sens de la marche dans le comparateur.

    L'operateur ne lit pas un signe : il lit "x doit descendre sous 605".

    Quatre decimales, comme `ligne_etat` en affiche pour la position du
    heros : l'operateur lit les deux sur la meme console, et un seuil arrondi
    a 605,2 en face d'un x=605,1900 se lirait comme atteint alors que le
    vrai seuil est 605,25. Le calcul, lui, a toujours ete exact -- c'est
    l'affichage qui cachait une precision que l'operateur a par ailleurs sous
    les yeux.
    """
    comparateur = ">=" if cible.sens == 1 else "<="
    return (
        f"cible : {cible.axe} {comparateur} {cible.seuil:.4f} "
        f"avant l'image {cible.image_limite}"
    )


def ligne_balayage(faits: int, total: int, resultat, reussis: int) -> str:
    """L'avancement du balayage, reecrit en place a chaque essai.

    Attend un `resultat` mesure : `progression` a None leve une TypeError sur
    le format. Aucun chemin d'appel ne le produit -- les couples impossibles
    sont notes des la construction du Balayage, donc `prochain` ne les rend
    jamais et `balayer` ne dit que des resultats fraichement notes -- et
    l'echec bruyant vaut mieux qu'une ligne qui inventerait un chiffre.
    """
    couple = resultat.couple
    marque = "REUSSI" if resultat.reussi else "      "
    return (
        f"balayage {faits:3d}/{total:3d} | "
        f"({couple.precedent:+d},{couple.travaille:+d}) | "
        f"{resultat.progression:10.4f} | {marque} | {reussis} reussi(s)"
    )


def lignes_podium(resultats) -> list[str]:
    """Les meilleurs essais, une chaine par ligne.

    Rend une liste et non une chaine a decouper, contrairement aux autres
    fonctions de ce module qui rendent chacune UNE ligne. Un `ligne_podium`
    qui joignait ses lignes obligeait l'appelant a les redecouper aussitot,
    et `ecrire_en_place` -- qui complete et tronque a LARGEUR_LIGNE -- ne
    sait de toute facon traiter qu'une ligne a la fois.
    """
    if not resultats:
        return ["aucun essai mesure"]
    lignes = ["podium :"]
    for rang, resultat in enumerate(resultats, 1):
        couple = resultat.couple
        marque = "  <-- atteint la cible" if resultat.reussi else ""
        lignes.append(
            f"  {rang}. ({couple.precedent:+d},{couple.travaille:+d}) "
            f"progression {resultat.progression:.4f}{marque}"
        )
    return lignes


def aide() -> str:
    return (
        "n         +1 image          Tab  +10 images        P  play / pause\n"
        "Espace    poser un saut a l'image courante\n"
        "haut/bas  choisir le saut a travailler\n"
        "gauche/droite  decaler ce saut d'une image\n"
        "Backspace retirer le saut choisi\n"
        "F1        relancer le jeu et repartir d'un film vide\n"
        "F2        essai rapide : sans relance, turbo jusqu'au saut travaille\n"
        "F3        essai de validation : avec relance, bit-exact\n"
        "F4        balayer les deux sauts autour du saut travaille\n"
        "F5        ecrire le film     T  turbo     Q  quitter"
    )


def ecrire_en_place(texte: str, sortie=None) -> None:
    """Reecrit la ligne courante du terminal.

    Le remplissage a LARGEUR_LIGNE efface la fin de la ligne precedente :
    sans lui, une ligne courte laisserait trainer la queue d'une longue.
    """
    sortie = sys.stdout if sortie is None else sortie
    sortie.write("\r" + texte.ljust(LARGEUR_LIGNE)[:LARGEUR_LIGNE])
    sortie.flush()
