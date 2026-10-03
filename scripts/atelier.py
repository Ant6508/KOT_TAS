# -*- coding: utf-8 -*-
"""atelier.py - la fenetre pour poser les runs.

MEmu a cote, la fenetre devant : les taps partent par adb, donc le jeu n'a
jamais besoin du focus.

Chaque essai relance le jeu (spec 2026-09-24). Le bandeau dit toujours dans
quel etat est le film et pourquoi ; la frise montre les sauts et la derniere
trace ; les boutons qui n'ont pas de sens sont grises. Aucune logique ici :
l'etat est dans controller/atelier.py, le travail dans controller/pilote.py.

Usage :
    python scripts/atelier.py
    python scripts/atelier.py films/reference.json
"""

import os
import queue
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Lance depuis scripts/, la racine du depot n'est pas dans sys.path.
RACINE_DEPOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE_DEPOT)

from controller.atelier import (  # noqa: E402
    BROUILLON,
    ESSAYE,
    GELE,
    Atelier,
    AtelierError,
    chemin_libre,
    nom_suggere,
)
from controller.frise import (  # noqa: E402
    Echelle,
    courbe,
    etendue,
    graduations,
    saut_proche,
)
from controller.movie import MovieError, load_movie  # noqa: E402
from controller.pilote import Pilote  # noqa: E402
from controller.run import LATENCE_TAP_IMAGES  # noqa: E402
from controller.session import EXPECTED_VERSION_CODE, Session  # noqa: E402

BADGES = {
    BROUILLON: ("BROUILLON", "#d9a300", "#000000"),
    ESSAYE: ("ESSAYÉ", "#22aa77", "#ffffff"),
    GELE: ("❄ GELÉ", "#3a6ed8", "#ffffff"),
}
ROUGE = "#dd4444"
BLEU = "#3399ff"
VERT = "#22aa77"
GRIS = "#888888"
VIOLET = "#8a4fd8"      # les points d'arret, distincts des sauts et du repere
ENCRE = "#222222"

HAUTEUR_FRISE = 180
BAS_FRISE = 22          # bande des graduations, sous la courbe
SCRUTATION_MS = 50
# Ancres a la racine du depot, pas au repertoire courant : lancee d'ailleurs,
# la fenetre ecrirait les films n'importe ou.
DOSSIER_FILMS = os.path.join(RACINE_DEPOT, "films")
FILM_NEUF = os.path.join(DOSSIER_FILMS, "run.json")

AIDE = ("clic : repère · double-clic : poser un saut · glisser un saut : le "
        "décaler · clic droit : retirer un saut ou un arrêt · ← → : décaler "
        "le saut choisi · Suppr : le retirer · Entrée : J'y suis")


class Fenetre:
    def __init__(self, racine, pilote, atelier=None):
        self.racine = racine
        self.pilote = pilote
        self.atelier = atelier if atelier is not None else Atelier()
        self.repere = None       # image choisie pour Poser au repère et Reprendre
        self.glisse = None       # (image de départ, image visée) d'un glissement
        self.occupe = False
        self.en_erreur = False
        self.image_en_cours = None
        # Vrai entre Ouvrir et la fin de la liberation du jeu qu'il demande.
        self.liberation = False
        # Vrai pendant l'attente de [J'y suis] : le bouton Interrompre y annule
        # l'essai, alors que pendant un deroule il met en pause.
        self.en_navigation = False
        self.jeu = "jeu : pas encore relancé par l'atelier"
        self.message = ("Essayer pour commencer : le jeu se relance, tu "
                        "navigues, puis le run se déroule.")
        self.turbo = tk.BooleanVar(value=True)
        self.echelle = Echelle(400, 1)
        self.boutons = {}
        self._construire()
        self.rafraichir()
        self._rappel = self.racine.after(SCRUTATION_MS, self._scruter)

    # ----- construction -----

    def _construire(self):
        r = self.racine
        r.title("Atelier TAS")

        bandeau = ttk.Frame(r, padding=8)
        bandeau.pack(fill="x")
        self.badge = tk.Label(bandeau, font=("Segoe UI", 18, "bold"),
                              padx=16, pady=10)
        self.badge.pack(side="left", fill="y")
        infos = ttk.Frame(bandeau, padding=(10, 0))
        infos.pack(side="left", fill="both", expand=True)
        self.ligne_film = tk.Label(infos, anchor="w", foreground=ENCRE)
        self.ligne_raison = tk.Label(infos, anchor="w", foreground=ENCRE)
        self.ligne_jeu = tk.Label(infos, anchor="w", foreground=ENCRE)
        self.ligne_position = tk.Label(infos, anchor="w", foreground=ENCRE)
        for ligne in (self.ligne_film, self.ligne_raison, self.ligne_jeu,
                     self.ligne_position):
            ligne.pack(fill="x")

        dialogue = ttk.Frame(r, padding=(8, 0))
        dialogue.pack(fill="x")
        self.ligne_message = tk.Label(dialogue, anchor="w", justify="left",
                                      wraplength=900, foreground=ENCRE)
        self.ligne_message.pack(side="left", fill="x", expand=True)
        self.bouton_y_suis = ttk.Button(dialogue, text="J'y suis",
                                        command=self.pilote.confirmer)

        self.frise = tk.Canvas(r, height=HAUTEUR_FRISE, background="#f4f4f4",
                               highlightthickness=0)
        self.frise.pack(fill="x", padx=8, pady=8)
        tk.Label(r, text=AIDE, foreground=GRIS, anchor="w").pack(fill="x",
                                                                  padx=8)
        c = self.frise
        c.bind("<Configure>", lambda e: self._dessiner())
        c.bind("<Button-1>", self._clic)
        c.bind("<B1-Motion>", self._glisser)
        c.bind("<ButtonRelease-1>", self._relacher)
        c.bind("<Double-Button-1>", self._double_clic)
        c.bind("<Button-3>", self._clic_droit)
        r.bind("<Left>", lambda e: self._editer(lambda: self.atelier.decaler(-1)))
        r.bind("<Right>", lambda e: self._editer(lambda: self.atelier.decaler(+1)))
        r.bind("<Delete>", lambda e: self._retirer_choisi())
        r.bind("<Return>", lambda e: self.pilote.confirmer())

        actions = ttk.Frame(r, padding=8)
        actions.pack(fill="x")
        poser = ttk.LabelFrame(actions, text="Poser", padding=6)
        poser.pack(side="left", padx=(0, 10))
        self._bouton(poser, "essayer", "▶ Essayer (relance)", self._essayer)
        self._bouton(poser, "avancer", "+1", lambda: self._avancer(1))
        self._bouton(poser, "avancer", "+10", lambda: self._avancer(10))
        self._bouton(poser, "sauter", "Sauter ici",
                     lambda: self._lancer(self.pilote.sauter))
        self._bouton(poser, "jusquau_bout", "Jouer jusqu'au bout",
                     self._jusquau_bout)
        self._bouton(poser, "poser", "Poser au repère", self._poser_au_repere)
        self._bouton(poser, "editer", "Retirer ce saut", self._retirer_choisi)
        self._bouton(poser, "reprendre", "Reprendre d'ici", self._reprendre)
        self._bouton(poser, "arret", "⏸ Arrêt au repère", self._arret_au_repere)
        ttk.Checkbutton(poser, text="turbo jusqu'au saut choisi",
                        variable=self.turbo).pack(side="left", padx=6)

        film = ttk.LabelFrame(actions, text="Film", padding=6)
        film.pack(side="left", padx=(0, 10))
        self._bouton(film, "ouvrir", "Ouvrir…", self.ouvrir)
        self._bouton(film, "geler", "❄ Geler", self._geler)
        self._bouton(film, "rejouer", "Rejouer", self._rejouer)
        self._bouton(film, "rejouer_encore", "Rejouer encore (sans relance)",
                     self._rejouer_encore)
        self._bouton(film, "degeler", "Dégeler", self._degeler)

        self._bouton(actions, "interrompre", "■ Interrompre",
                     self.pilote.interrompre)

    def _bouton(self, parent, action, texte, commande):
        bouton = ttk.Button(parent, text=texte, command=commande)
        bouton.pack(side="left", padx=2)
        self.boutons.setdefault(action, []).append(bouton)

    # ----- affichage -----

    def _permis(self):
        permis = self.atelier.actions(self.occupe, self.pilote.tete)
        permis["poser"] = permis["poser"] and self.repere is not None
        permis["reprendre"] = permis["reprendre"] and self.repere is not None
        permis["editer"] = (permis["editer"]
                            and self.atelier.film.choisi is not None)
        permis["arret"] = permis["arret"] and self.repere is not None
        return permis

    def _decrire_film(self):
        a = self.atelier
        if a.chemin:
            nom = a.chemin
        elif a.source:
            nom = f"copie de travail de {a.source}"
        else:
            nom = "nouveau film, pas encore enregistré"
        return (f"Film : {nom} · {len(a.film.sauts)} saut(s) · "
                f"{a.longueur} images")

    def _decrire_position(self):
        """La derniere position connue du heros, tiree de la trace notee.

        `a.trace` n'avance qu'aux pauses (spec pilote) : entre deux, la
        position affichee reste celle de la derniere pause, pas celle de
        l'image en cours de deroule.
        """
        if not self.atelier.trace:
            courante = "héros : position inconnue"
        else:
            etat = self.atelier.trace[-1]
            courante = f"héros : x={etat.x:.4f} y={etat.y:.4f} (image {etat.frame})"
        saut = self._decrire_position_saut()
        return courante if saut is None else f"{courante} · {saut}"

    def _decrire_position_saut(self):
        """La position du heros au saut choisi, tiree de la trace notee.

        None si aucun saut n'est choisi. `a.trace[image]` est l'etat d'avant
        cette image (meme convention que `longueur_requise`), donc la
        position du heros au moment ou ce saut part.
        """
        a = self.atelier
        choisi = a.film.choisi
        if choisi is None:
            return None
        rang = a.film.sauts.index(choisi) + 1
        if choisi >= len(a.trace):
            return f"saut {rang} (image {choisi}) : position pas encore connue"
        etat = a.trace[choisi]
        return f"saut {rang} (image {choisi}) : x={etat.x:.4f} y={etat.y:.4f}"

    def rafraichir(self):
        a = self.atelier
        texte, fond, encre = BADGES[a.etat]
        self.badge.configure(text=texte, background=fond, foreground=encre)
        self.ligne_film.configure(text=self._decrire_film())
        self.ligne_raison.configure(text=f"Pourquoi : {a.raison}")
        self.ligne_jeu.configure(text=self.jeu,
                                 foreground=ROUGE if self.en_erreur else ENCRE)
        self.ligne_position.configure(text=self._decrire_position())
        self.ligne_message.configure(text=self.message)
        permis = self._permis()
        for action, boutons in self.boutons.items():
            for bouton in boutons:
                bouton.configure(
                    state="normal" if permis[action] else "disabled")
        # Pause seulement quand le run reste en pause apres l'arret : un passage
        # de film gele interrompu, lui, rend le jeu.
        pause = self.occupe and not self.en_navigation and not a.gele
        self.boutons["interrompre"][0].configure(
            text="⏸ Pause" if pause else "■ Interrompre")
        self._dessiner()

    def _dessiner(self):
        c = self.frise
        c.delete("all")
        a = self.atelier
        tete = self.image_en_cours if self.occupe else self.pilote.tete
        images = etendue(a.longueur_requise, max(len(a.trace), tete or 0),
                         list(a.film.sauts) + sorted(a.arrets))
        self.echelle = e = Echelle(max(c.winfo_width(), 100), images)
        bas = HAUTEUR_FRISE - BAS_FRISE

        for k in graduations(images):
            c.create_line(e.x(k), bas, e.x(k), bas + 5, fill=GRIS)
            c.create_text(e.x(k), HAUTEUR_FRISE - 2, text=str(k), anchor="s",
                          fill=GRIS)

        points = courbe([etat.y for etat in a.trace], e, bas)
        if len(points) >= 2:
            style = {"dash": (5, 3)} if a.etat == BROUILLON else {}
            c.create_line(*[v for p in points for v in p], fill=VERT, width=2,
                          **style)

        choisi = a.film.choisi
        for rang, saut in enumerate(a.film.sauts, 1):
            x = e.x(saut)
            c.create_line(x, 4, x, bas, fill=ROUGE,
                          width=4 if saut == choisi else 2)
            decollage = e.x(saut + LATENCE_TAP_IMAGES)
            c.create_line(decollage, bas - 10, decollage, bas, fill=ROUGE)
            c.create_text(x + 4, 6, text=f"{rang} · {saut}", anchor="nw",
                          fill=ROUGE,
                          font=("Segoe UI", 9,
                                "bold" if saut == choisi else "normal"))

        for arret in sorted(a.arrets):
            x = e.x(arret)
            c.create_line(x, 4, x, bas, fill=VIOLET, width=2, dash=(4, 2))
            c.create_text(x + 4, bas - 18, text=f"⏸ {arret}", anchor="sw",
                          fill=VIOLET)
        if self.glisse is not None:
            x = e.x(self.glisse[1])
            c.create_line(x, 4, x, bas, fill=ROUGE, dash=(3, 3))
        if self.repere is not None:
            x = e.x(self.repere)
            c.create_line(x, 0, x, bas, fill=VERT, dash=(2, 2))
            c.create_text(x + 4, bas - 4, text=f"repère {self.repere}",
                          anchor="sw", fill=VERT)
        if tete is not None:
            x = e.x(tete)
            c.create_line(x, 0, x, HAUTEUR_FRISE, fill=BLEU, width=2)

    # ----- la frise -----

    def _clic(self, evenement):
        if self.occupe:
            return
        saut = saut_proche(self.atelier.film.sauts, evenement.x, self.echelle)
        if saut is not None:
            self.atelier.choisir(saut)
            if not self.atelier.gele:
                self.glisse = (saut, saut)
        else:
            self.repere = self.echelle.image(evenement.x)
        self.rafraichir()

    def _glisser(self, evenement):
        if self.glisse is not None:
            self.glisse = (self.glisse[0], self.echelle.image(evenement.x))
            self._dessiner()

    def _relacher(self, evenement):
        if self.glisse is None:
            return
        de, vers = self.glisse
        self.glisse = None
        if vers != de:
            self._editer(lambda: self.atelier.deplacer(de, vers))
        else:
            self.rafraichir()

    def _double_clic(self, evenement):
        if self.occupe or self.atelier.gele:
            return
        if saut_proche(self.atelier.film.sauts, evenement.x,
                       self.echelle) is None:
            image = self.echelle.image(evenement.x)
            self.repere = image
            self._editer(lambda: self.atelier.poser(image))

    def _clic_droit(self, evenement):
        # Le marqueur le plus proche, saut ou arret ; a image egale, le saut.
        a = self.atelier
        marque = saut_proche(list(a.film.sauts) + sorted(a.arrets),
                             evenement.x, self.echelle)
        if marque is None:
            return
        if marque in a.film.sauts:
            self._editer(lambda: a.retirer(marque))
        else:
            self._editer(lambda: a.retirer_arret(marque))

    def _editer(self, action):
        if self.occupe:
            return
        try:
            action()
        except AtelierError as exc:
            self.message = str(exc)
        self.rafraichir()

    def _poser_au_repere(self):
        image = self.repere
        self._editer(lambda: self.atelier.poser(image))

    def _arret_au_repere(self):
        image = self.repere
        self._editer(lambda: self.atelier.poser_arret(image))

    def _retirer_choisi(self):
        choisi = self.atelier.film.choisi
        if choisi is not None:
            self._editer(lambda: self.atelier.retirer(choisi))

    # ----- les commandes du pilote -----

    def _lancer(self, commande):
        try:
            commande()
        except RuntimeError as exc:
            self.message = str(exc)
        else:
            self.occupe = True
        self.rafraichir()

    def _frontiere(self, jusqua):
        if not self.turbo.get():
            return None
        return self.atelier.frontiere_turbo(jusqua)

    def _essayer(self):
        # La longueur requise, pas la longueur : sur un film neuf elle vaut 0,
        # et l'essai ne jouerait aucun des sauts poses. Puis le premier point
        # d'arret sur le chemin.
        a = self.atelier
        jusqua = a.borne(0, a.longueur_requise)
        self._lancer(lambda: self.pilote.essayer(
            a.film.sauts, jusqua, self._frontiere(jusqua), a.depart))

    def _reprendre(self):
        a = self.atelier
        jusqua = a.borne(0, self.repere)
        self._lancer(lambda: self.pilote.essayer(
            a.film.sauts, jusqua, self._frontiere(jusqua), a.depart))

    def _avancer(self, images):
        tete = self.pilote.tete
        if tete is None:
            return   # plus de run en pause : rien a prolonger
        a = self.atelier
        jusqua = a.borne(tete, tete + images)
        self._lancer(lambda: self.pilote.avancer(a.film.sauts, jusqua))

    def _jusquau_bout(self):
        tete = self.pilote.tete
        if tete is None:
            return
        a = self.atelier
        jusqua = a.borne(tete, a.longueur_requise)
        self._lancer(lambda: self.pilote.avancer(a.film.sauts, jusqua))

    def _rejouer(self):
        self._lancer(lambda: self.pilote.rejouer(self.atelier.movie))

    def _rejouer_encore(self):
        a = self.atelier
        self._lancer(lambda: self.pilote.rejouer_encore(a.movie,
                                                        a.passages + 1))

    # ----- les evenements du pilote -----

    def _scruter(self):
        # Toujours reprogrammee, et une erreur de la fenetre s'affiche au
        # lieu de remonter : sans quoi la scrutation s'arrete en silence, et
        # la fenetre ne voit plus jamais rien du pilote.
        try:
            while True:
                try:
                    ev = self.pilote.evenements.get_nowait()
                except queue.Empty:
                    break
                try:
                    self._recevoir(ev)
                except Exception as exc:  # noqa: BLE001 -- voir plus haut
                    self.message = (f"erreur de la fenêtre sur l'événement "
                                    f"{ev.genre} : {exc}")
                    try:
                        self.rafraichir()
                    except Exception:  # noqa: BLE001
                        pass
        finally:
            self._rappel = self.racine.after(SCRUTATION_MS, self._scruter)

    def arreter(self):
        """Annule la scrutation, sans quoi elle survit a la fenetre detruite."""
        self.racine.after_cancel(self._rappel)

    def _recevoir(self, ev):
        a = self.atelier
        if ev.genre == "occupe":
            self.occupe = True
            self.en_erreur = False
            self.jeu = "jeu : opération en cours"
        elif ev.genre == "libre":
            self.occupe = False
            self.en_navigation = False
            self.image_en_cours = None
            self.liberation = False
            self.bouton_y_suis.pack_forget()
            # Recalcule depuis le pilote : c'est lui qui sait si un run est
            # encore en pause. Une erreur, elle, reste affichee.
            if not self.en_erreur:
                tete = self.pilote.tete
                self.jeu = ("jeu : rendu à l'opérateur" if tete is None
                            else f"jeu : en pause à l'image {tete}")
        elif ev.genre == "message":
            # La liberation demandee par Ouvrir dirait "jeu rendu" par-dessus
            # le message d'ouverture ; la ligne jeu le dira a `libre`.
            if not (self.liberation
                    and ev.texte == "jeu rendu a l'operateur"):
                self.message = ev.texte
        elif ev.genre == "navigation":
            self.message = ev.texte
            self.en_navigation = True
            # Pas "relance" : Rejouer encore attend aussi [J'y suis], sans
            # avoir relance le jeu.
            self.jeu = "jeu : attente de navigation"
            self.bouton_y_suis.pack(side="right")
        elif ev.genre == "image":
            self.en_navigation = False
            self.image_en_cours = ev.image
            self.jeu = f"jeu : déroulé en cours, image {ev.image}"
        elif ev.genre == "trace":
            self.en_navigation = False
            self.bouton_y_suis.pack_forget()
            if ev.saut is not None:
                a.sauter_en_direct(ev.saut)
            a.noter_trace(ev.trace, ev.entrees, ev.depart, ev.cycle, ev.fin)
            self.jeu = f"jeu : en pause à l'image {ev.image}"
            self.message = ev.texte
            if ev.image in a.arrets:
                self.message = (f"⏸ arrêt à l'image {ev.image} : Jouer "
                                f"jusqu'au bout pour continuer")
        elif ev.genre == "passage":
            self.message = a.noter_passage(ev.numero, ev.empreinte)
            self.jeu = "jeu : rendu à l'opérateur"
        elif ev.genre == "erreur":
            if a.gele:
                # Le passage a rate : le jeu ne compte plus deux reussites
                # d'affilee, le suivant doit repartir d'une relance.
                a.passage_reussi = False
            self.en_erreur = True
            self.message = ev.texte
            self.jeu = ("jeu perdu : Essayer relancera proprement" if ev.perdu
                        else "jeu : rendu à l'opérateur")
        self.rafraichir()

    # ----- les films -----

    def ouvrir(self, chemin=None):
        if self.occupe:
            return
        if self.atelier.a_perdre and not messagebox.askyesno(
                "Ouvrir", "La copie de travail n'est pas gelée : "
                          "l'abandonner ?", parent=self.racine):
            return
        if chemin is None:
            chemin = filedialog.askopenfilename(
                parent=self.racine, initialdir=DOSSIER_FILMS,
                filetypes=[("Films", "*.json")])
            if not chemin:
                return
        try:
            movie = load_movie(chemin, EXPECTED_VERSION_CODE)
        except Exception as exc:  # noqa: BLE001 -- un JSON d'une autre forme
            # leve TypeError, KeyError... : tout refus finit dans le bandeau.
            self.message = f"ouverture refusée : {exc}"
            self.rafraichir()
            return
        if self.pilote.tete is not None:
            self._lancer(self.pilote.liberer)
            self.liberation = self.occupe
        self.atelier = Atelier.depuis_film(movie, chemin)
        self.repere = None
        self.message = "Film gelé ouvert. Rejouer : 1er passage, avec relance."
        self.rafraichir()

    def _degeler(self):
        self._editer(self.atelier.degeler)
        self.message = ("Copie de travail : l'original ne sera remplacé que si "
                        "tu choisis de l'écraser au prochain gel.")
        self.rafraichir()

    def _geler(self):
        a = self.atelier
        dialogue = tk.Toplevel(self.racine)
        dialogue.title("Geler le film")
        dialogue.transient(self.racine)
        dialogue.grab_set()
        cadre = ttk.Frame(dialogue, padding=12)
        cadre.pack(fill="both", expand=True)

        ttk.Label(cadre, text="Issue du run :").pack(anchor="w")
        # Aucune issue par defaut : un Enregistrer machinal gelerait une
        # victoire qui n'a peut-etre pas eu lieu.
        issue = tk.StringVar(value="")
        for code, texte in (("win", "Victoire"), ("death", "Mort"),
                            ("incomplete", "Incomplet")):
            ttk.Radiobutton(cadre, text=texte, value=code,
                            variable=issue).pack(anchor="w")
        ttk.Label(cadre, text="Étiquette :").pack(anchor="w", pady=(8, 0))
        label = tk.StringVar(value=a.label)
        ttk.Entry(cadre, textvariable=label, width=40).pack(fill="x")

        def ecrire(chemin):
            if self._geler_vers(chemin, issue.get(), label.get(), dialogue):
                dialogue.destroy()

        boutons = ttk.Frame(cadre, padding=(0, 10, 0, 0))
        boutons.pack(fill="x")
        if a.source:
            suggestion = nom_suggere(a.source)
            ttk.Button(boutons, text=f"Écraser {a.source}",
                       command=lambda: ecrire(a.source)).pack(fill="x")
            ttk.Button(boutons, text=f"Enregistrer sous {suggestion}",
                       command=lambda: ecrire(suggestion)).pack(fill="x")
        else:
            ttk.Label(cadre, text="Fichier :").pack(anchor="w", pady=(8, 0),
                                                    before=boutons)
            chemin = tk.StringVar(value=chemin_libre(FILM_NEUF))
            ttk.Entry(cadre, textvariable=chemin, width=40).pack(
                fill="x", before=boutons)

            def enregistrer():
                cible = chemin.get().strip()
                if os.path.exists(cible) and not messagebox.askyesno(
                        "Geler", f"{cible} existe déjà. L'écraser ?",
                        parent=dialogue):
                    return
                ecrire(cible)

            ttk.Button(boutons, text="Enregistrer",
                       command=enregistrer).pack(fill="x")
        ttk.Button(boutons, text="Annuler",
                   command=dialogue.destroy).pack(fill="x", pady=(6, 0))

    def _geler_vers(self, chemin, issue, label, parent):
        """Gele le film dans `chemin`. Rend False si le gel est refuse."""
        a = self.atelier
        if not issue:
            messagebox.showerror("Geler", "choisis l'issue du run : victoire, "
                                          "mort ou incomplet", parent=parent)
            return False
        # Le gel ne compte comme 1er passage que si le run de la trace est
        # encore en pause a son bout : c'est lui que Rejouer encore rendra.
        tete = self.pilote.tete
        premier = tete is not None and tete == len(a.trace)
        try:
            a.geler(chemin, issue, label, premier_passage=premier)
        except (AtelierError, MovieError, OSError) as exc:
            messagebox.showerror("Geler", str(exc), parent=parent)
            return False
        if premier:
            self.message = (f"Film gelé : {chemin}. Rejouer encore (sans "
                            f"relance) pour la deuxième réussite du donjon.")
        else:
            self.message = (f"Film gelé : {chemin}. Le run n'est plus en "
                            f"pause : Rejouer (avec relance) pour le 1er "
                            f"passage.")
        self.rafraichir()
        return True

    def fermer(self):
        if self.atelier.a_perdre and not messagebox.askyesno(
                "Quitter", "La copie de travail n'est pas gelée. Quitter "
                           "quand même ?", parent=self.racine):
            return
        self.pilote.fermer()
        self.arreter()
        self.racine.destroy()


def main():
    racine = tk.Tk()
    fenetre = Fenetre(racine, Pilote(Session()))
    if len(sys.argv) > 1:
        fenetre.ouvrir(sys.argv[1])
    racine.protocol("WM_DELETE_WINDOW", fenetre.fermer)
    racine.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
