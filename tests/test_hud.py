import io

from controller.cible import Cible
from controller.hud import (
    LARGEUR_LIGNE,
    aide,
    ecrire_en_place,
    ligne_balayage,
    ligne_cible,
    ligne_decalage,
    ligne_etat,
    ligne_issue,
    ligne_saut,
    ligne_sauts,
    lignes_podium,
)
from controller.solveur import Couple, Resultat
from controller.trace import Etat


ETAT = Etat(frame=142, x=786.5624, y=505.0718, vx=0.0, vy=-8.2102)


def test_la_ligne_d_etat_porte_l_image_la_position_et_le_mode():
    assert ligne_etat(142, ETAT, sauts=3, en_pause=True) == (
        "image   142 | x=  786.5624 y=  505.0718 vx=  0.0000 vy= -8.2102 "
        "| 3 saut(s) | PAUSE"
    )


def test_la_ligne_d_etat_dit_le_turbo():
    ligne = ligne_etat(10, ETAT, sauts=0, en_pause=False, turbo=True)
    assert ligne.endswith("| 0 saut(s) | MARCHE+TURBO")


def test_sans_image_enregistree_la_ligne_le_dit_au_lieu_d_inventer():
    assert ligne_etat(0, None, sauts=0, en_pause=True) == (
        "image     0 | aucune image enregistree | 0 saut(s) | PAUSE"
    )


def test_la_ligne_de_saut_montre_les_deux_images():
    assert ligne_saut(100, 102) == (
        "saut pose a l'image 100 -> decollage attendu a l'image 102"
    )


def test_la_ligne_d_issue_nomme_l_image_de_la_mort():
    assert ligne_issue("death", 128) == (
        "le heros a disparu a l'image 128 : le run s'arrete la"
    )


def test_la_ligne_d_issue_d_un_run_qui_continue():
    assert ligne_issue("incomplete", None) == (
        "run incomplet : le heros est toujours la"
    )


def test_l_aide_liste_les_touches_de_l_editeur():
    texte = aide()
    for attendu in ("F1", "F2", "F3", "F5", "Espace", "Tab", "Backspace", "n"):
        assert attendu in texte


def test_l_ecriture_en_place_revient_au_debut_et_efface_la_ligne_precedente():
    sortie = io.StringIO()

    ecrire_en_place("court", sortie)

    ecrit = sortie.getvalue()
    assert ecrit.startswith("\r")
    assert len(ecrit) == 1 + LARGEUR_LIGNE
    assert ecrit.strip() == "court"


def test_la_ligne_des_sauts_marque_celui_qu_on_travaille():
    assert ligne_sauts([66, 174, 211, 250, 284], 2) == (
        "sauts  66  174  [211]  250  284"
    )


def test_la_ligne_des_sauts_d_un_film_vide_dit_quoi_faire():
    assert ligne_sauts([], None) == (
        "sauts  aucun -- Espace en pose un a l'image courante"
    )


def test_la_ligne_de_decalage_montre_les_trois_nombres():
    """Les deux images du saut, et celle du decollage : aucune convention ne
    doit rester implicite."""
    assert ligne_decalage(3, 211, 212, 214) == (
        "saut 3 : 211 -> 212 (decollage attendu a l'image 214)"
    )


def test_la_ligne_de_cible_dit_le_sens_de_la_marche():
    assert ligne_cible(Cible("x", -1, 605.25, 300)) == (
        "cible : x <= 605.2500 avant l'image 300"
    )
    assert ligne_cible(Cible("y", 1, 120.0, 40)) == (
        "cible : y >= 120.0000 avant l'image 40"
    )


def test_la_ligne_de_balayage_porte_l_avancement_et_le_verdict():
    resultat = Resultat(Couple(-1, 2), progression=-452.25, reussi=True)

    assert ligne_balayage(17, 49, resultat, reussis=3) == (
        "balayage  17/ 49 | (-1,+2) |  -452.2500 | REUSSI | 3 reussi(s)"
    )


def test_un_essai_rate_ne_porte_pas_la_marque():
    resultat = Resultat(Couple(0, 0), progression=-700.0, reussi=False)

    assert "REUSSI" not in ligne_balayage(1, 49, resultat, reussis=0)


def test_le_podium_numerote_et_marque_ceux_qui_atteignent_la_cible():
    resultats = [
        Resultat(Couple(0, 1), progression=-500.0, reussi=True),
        Resultat(Couple(0, 0), progression=-700.0, reussi=False),
    ]

    lignes = lignes_podium(resultats)

    assert lignes[0] == "podium :"
    assert lignes[1] == "  1. (+0,+1) progression -500.0000  <-- atteint la cible"
    assert lignes[2] == "  2. (+0,+0) progression -700.0000"


def test_un_podium_vide_le_dit():
    assert lignes_podium([]) == ["aucun essai mesure"]


def test_l_aide_annonce_la_touche_du_balayage():
    assert "F4" in aide()
