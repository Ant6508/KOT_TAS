"""Format de film : la sequence d'entrees d'un run, et sa validation.

Un film accepte a tort produit un rejeu faux et silencieux, ce qui est le mode
de panne le plus couteux de l'outil. La validation est donc stricte et les
refus sont explicites.

Version 2 (spec 1 ter J). Trois champs s'ajoutent, un disparait :

- `anchor` dit sur quoi tombe l'image 0. Une seule valeur admise aujourd'hui,
  mais le champ existe pour qu'un film enregistre sous une convention future
  soit refuse plutot que rejoue de travers.
- `start` porte les conditions de depart. Un film n'est rejouable au bit pres
  que depuis un jeu fraichement lance : la derive de la position de depart
  s'accumule par entree de donjon et ne se remet a zero qu'au relancement
  (NOTES.md, jalon 5).
- `clock` porte le cycle de l'horloge virtuelle. Une empreinte enregistree
  horloge active ne veut rien dire sans elle.
- `hold` est retire. `adb input tap` emet l'appui et le relachement dans la
  meme image : le champ decrivait une chose qu'on ne sait pas produire.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

MOVIE_FORMAT_VERSION = 2

# Seule valeur admise pour `anchor`. L'image 0 est la premiere image relachee
# depuis l'ecran de commencement, ou le heros est deja charge et ou le tap
# suivant demarre le niveau.
ANCRAGE_COMMENCEMENT = "commencement"
ANCRAGES_CONNUS = (ANCRAGE_COMMENCEMENT,)

# Le cycle du delta de frame impose a nativeDrawFrame. 16, 17, 17 et non une
# constante : le moteur depense 16,667 ms par pas, donc 17 constant laisserait
# 0,33 ms d'excedent par image, soit un pas de trop toutes les cinquante
# images. Voir agent/pump.js et NOTES.md, "La source de temps du jeu".
CYCLE_HORLOGE_MS = (16, 17, 17)

ISSUES_CONNUES = ("win", "death", "incomplete")


class MovieError(Exception):
    """Le film est malforme ou incoherent."""


class IncompatibleMovie(MovieError):
    """Le film a ete enregistre dans des conditions qu'on ne reproduit pas."""


@dataclass(frozen=True)
class GameBuild:
    package: str
    version_name: str
    version_code: int


@dataclass(frozen=True)
class TapInput:
    """Un tap, date a l'image ou il est EMIS, barriere fermee.

    Le heros decolle deux pas plus tard (NOTES.md, jalon 5, section 5). C'est
    l'emission qui est reproductible, donc c'est elle qu'on stocke.
    """

    frame: int


@dataclass(frozen=True)
class StartConditions:
    """Conditions de depart d'un run, sans lesquelles l'empreinte ne veut rien
    dire.

    `hero_x` et `hero_y` sont la position du heros a l'ecran de commencement,
    relevee a l'enregistrement. Elle sert a deux choses : attendre sans
    intervention que l'operateur y soit revenu, et refuser le rejeu si le
    donjon a change de forme -- auquel cas l'empreinte ne vaudrait plus.
    """

    relaunch: bool = True
    tap_demarrage: bool = True
    hero_x: float | None = None
    hero_y: float | None = None


@dataclass
class Movie:
    game: GameBuild
    dt: float
    run_frames: int
    anchor: str = ANCRAGE_COMMENCEMENT
    start: StartConditions = field(default_factory=StartConditions)
    clock_cycle_ms: tuple[int, ...] = CYCLE_HORLOGE_MS
    run_kind: str = "own_base_test"
    run_label: str = ""
    inputs: list[TapInput] = field(default_factory=list)
    outcome_status: str = "incomplete"
    outcome_frame: int | None = None
    fingerprint: str | None = None

    def __post_init__(self) -> None:
        if self.dt <= 0.0:
            raise MovieError(f"dt doit etre strictement positif, recu {self.dt}")
        if self.run_frames <= 0:
            raise MovieError(
                f"un film couvre au moins une image, recu {self.run_frames}"
            )
        if self.outcome_status not in ISSUES_CONNUES:
            raise MovieError(f"issue inconnue : {self.outcome_status}")
        if self.anchor not in ANCRAGES_CONNUS:
            raise MovieError(
                f"ancrage inconnu : {self.anchor}. Seul {ANCRAGE_COMMENCEMENT} "
                f"est admis en version {MOVIE_FORMAT_VERSION}."
            )
        self.clock_cycle_ms = tuple(self.clock_cycle_ms)
        if not self.clock_cycle_ms or any(ms <= 0 for ms in self.clock_cycle_ms):
            raise MovieError(
                f"cycle d'horloge invalide : {self.clock_cycle_ms}. Sans lui, "
                f"l'empreinte n'est pas reproductible."
            )
        self.inputs = self._validated(self.inputs)

    def _validated(self, inputs: list[TapInput]) -> list[TapInput]:
        seen: set[int] = set()
        for item in inputs:
            if item.frame < 0:
                raise MovieError(f"frame negative : {item.frame}")
            # L'egalite est admise, et ce n'est pas un oubli : poser un saut a
            # l'image N puis ecrire le film sans avancer donne exactement
            # frame == run_frames. Le tap est alors emis mais n'a pas eu le
            # temps d'agir sur la trace, ce qui est un film legitime.
            if item.frame > self.run_frames:
                raise MovieError(
                    f"saut programme a l'image {item.frame}, mais le film n'en "
                    f"compte que {self.run_frames} : il ne serait jamais joue, "
                    f"et l'empreinte ne vaudrait pas pour lui"
                )
            if item.frame in seen:
                raise MovieError(f"deux sauts programmes a la frame {item.frame}")
            seen.add(item.frame)
        return sorted(inputs, key=lambda i: i.frame)

    def add_tap(self, frame: int) -> None:
        self.inputs = self._validated([*self.inputs, TapInput(frame)])
        self.fingerprint = None

    def undo_last_tap(self) -> None:
        """Retire le saut de plus grande frame.

        Les entrees etant toujours triees, "le dernier" designe le saut le
        plus tardif, pas le dernier ajoute. En pratique les sauts s'ajoutent
        dans l'ordre chronologique, donc les deux coincident.
        """
        if self.inputs:
            self.inputs = self.inputs[:-1]
            self.fingerprint = None

    def to_dict(self) -> dict:
        return {
            "version": MOVIE_FORMAT_VERSION,
            "game": {
                "package": self.game.package,
                "versionName": self.game.version_name,
                "versionCode": self.game.version_code,
            },
            "dt": self.dt,
            "clock": {"cycle_ms": list(self.clock_cycle_ms)},
            "anchor": self.anchor,
            "start": {
                "relaunch": self.start.relaunch,
                "tap_demarrage": self.start.tap_demarrage,
                "hero_x": self.start.hero_x,
                "hero_y": self.start.hero_y,
            },
            "run": {
                "kind": self.run_kind,
                "label": self.run_label,
                "frames": self.run_frames,
            },
            "inputs": [{"frame": i.frame} for i in self.inputs],
            "outcome": {
                "status": self.outcome_status,
                "frame": self.outcome_frame,
            },
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Movie":
        version = data.get("version")
        if version != MOVIE_FORMAT_VERSION:
            raise MovieError(
                f"film en version {version}, attendu "
                f"{MOVIE_FORMAT_VERSION}. Les numeros d'image et les "
                f"conditions de depart ne se transposent pas d'une version "
                f"de format a l'autre."
            )
        try:
            game_data = data["game"]
            game = GameBuild(
                package=game_data["package"],
                version_name=game_data["versionName"],
                version_code=game_data["versionCode"],
            )
            start_data = data["start"]
            run_data = data["run"]
            outcome = data.get("outcome", {})
            return cls(
                game=game,
                dt=data["dt"],
                run_frames=run_data["frames"],
                anchor=data["anchor"],
                start=StartConditions(
                    relaunch=start_data["relaunch"],
                    tap_demarrage=start_data["tap_demarrage"],
                    hero_x=start_data["hero_x"],
                    hero_y=start_data["hero_y"],
                ),
                clock_cycle_ms=tuple(data["clock"]["cycle_ms"]),
                run_kind=run_data.get("kind", "own_base_test"),
                run_label=run_data.get("label", ""),
                inputs=[TapInput(frame=i["frame"]) for i in data.get("inputs", [])],
                outcome_status=outcome.get("status", "incomplete"),
                outcome_frame=outcome.get("frame"),
                fingerprint=data.get("fingerprint"),
            )
        except KeyError as exc:
            raise MovieError(f"champ absent du film : {exc.args[0]}") from exc


def verifier_rejouable(movie: Movie, cycle_ms: tuple[int, ...]) -> None:
    """Refuse de rejouer un film dans d'autres conditions que les siennes.

    Un rejeu approximatif produirait une empreinte differente sans qu'on
    sache si c'est le jeu ou le dispositif qui a change. Mieux vaut refuser.
    """
    if tuple(movie.clock_cycle_ms) != tuple(cycle_ms):
        raise IncompatibleMovie(
            f"film enregistre avec le cycle d'horloge "
            f"{list(movie.clock_cycle_ms)}, mais l'agent impose "
            f"{list(cycle_ms)}. Le temps de jeu ne serait pas le meme."
        )
    if movie.start.hero_x is None or movie.start.hero_y is None:
        raise IncompatibleMovie(
            "film sans position de depart : on ne saurait pas reconnaitre "
            "l'ecran de commencement, et l'image 0 pourrait tomber n'importe "
            "ou. Reenregistre-le."
        )


def save_movie(movie: Movie, path: str | Path) -> None:
    chemin = Path(path)
    # Le dossier des films n'existe pas forcement a la premiere ecriture, et
    # perdre un run soigne sur un FileNotFoundError serait absurde.
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        json.dumps(movie.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf8",
    )


def load_movie(path: str | Path, expected_version_code: int) -> Movie:
    try:
        data = json.loads(Path(path).read_text(encoding="utf8"))
    except json.JSONDecodeError as exc:
        raise MovieError(f"film illisible : {exc}") from exc

    movie = Movie.from_dict(data)

    if movie.game.version_code != expected_version_code:
        raise IncompatibleMovie(
            f"film enregistre sur la version {movie.game.version_name} "
            f"(versionCode {movie.game.version_code}), mais la version "
            f"installee attend le versionCode {expected_version_code}. "
            f"Les numeros de frame ne sont pas transposables."
        )

    return movie
