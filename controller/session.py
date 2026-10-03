"""Attache Frida au jeu et charge l'agent.

Refuse de demarrer si la version installee n'est pas celle attendue : un agent
qui pointe sur de mauvaises adresses fait plus de degats qu'un agent qui ne
demarre pas.
"""

from __future__ import annotations

import threading
import time

import frida

from controller.agent import build_agent_source
from controller.device import (
    PACKAGE,
    DeviceError,
    GameNotRunning,
    active_serial,
    ensure_frida_server_running,
    game_pid,
    installed_version,
    message_frida_discordant,
)

EXPECTED_VERSION_CODE = 4755781
EXPECTED_VERSION_NAME = "2.84"


class SessionError(Exception):
    """L'attache ou le chargement de l'agent a echoue."""


class Session:
    def __init__(self, package: str = PACKAGE) -> None:
        self.package = package
        self.session: frida.core.Session | None = None
        self.script: frida.core.Script | None = None
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    def verifier_frida(self) -> None:
        """Refuse un frida installe qui n'est pas celui de frida-server.

        Sinon l'attache echoue plus loin sur une erreur de protocole qui ne
        dit pas que la cause est une version.
        """
        discordance = message_frida_discordant(frida.__version__)
        if discordance is not None:
            raise SessionError(discordance)

    def check_version(self) -> None:
        name, code = installed_version(self.package)
        if code != EXPECTED_VERSION_CODE:
            raise SessionError(
                f"version de jeu inattendue : {name} (versionCode {code}), "
                f"attendu {EXPECTED_VERSION_NAME} (versionCode "
                f"{EXPECTED_VERSION_CODE}). Les symboles et offsets releves "
                f"dans NOTES.md ne valent que pour la version attendue."
            )

    def _attach_to(self, device):
        """Attache par nom, puis par pid. Voir NOTES.md : le nom ne suffit pas.

        Un DeviceError qui n'est pas GameNotRunning vient d'un echec adb
        (hors ligne, non autorise, serveur adb mort...) : on le laisse
        remonter tel quel, il ne veut pas dire que le jeu est arrete.
        """
        try:
            return device.attach(self.package)
        except frida.ProcessNotFoundError:
            try:
                pid = game_pid(self.package)
            except GameNotRunning as exc:
                raise SessionError(
                    f"{self.package} ne tourne pas. Lance le jeu dans MEmu."
                ) from exc

            try:
                return device.attach(pid)
            except frida.ProcessNotFoundError as exc:
                raise SessionError(
                    f"{self.package} (pid {pid}) a disparu entre la "
                    "recherche du pid et l'attache. Reessaie."
                ) from exc

    def attach(self) -> None:
        self.verifier_frida()
        self.check_version()
        ensure_frida_server_running()

        # Frida nomme un appareil adb par son serial : on vise le meme que
        # adb, et non le premier venu, sans quoi deux instances MEmu ouvertes
        # separeraient l'attache et les taps.
        device = frida.get_device(active_serial(), timeout=5)
        self.session = self._attach_to(device)

        self.script = self.session.create_script(build_agent_source())
        self.script.on("message", self._on_message)
        self.script.load()

        missing = self.script.exports_sync.symbols()["missing"]
        if missing:
            # `missing` melange deux pannes : un symbole absent, et un offset
            # qui resout mais ne pointe pas sur ce qu'il devrait. Les appeler
            # toutes "symboles non resolus" induirait en erreur.
            raise SessionError(
                "l'agent refuse de demarrer. Symboles absents ou offsets "
                "invalides :\n  - " + "\n  - ".join(missing)
            )

        self._start_heartbeat()

    def attacher_avec_reessais(
        self,
        essais: int = 15,
        delai: float = 1.0,
        dormir=time.sleep,
    ) -> None:
        """Attache en reessayant, apres un relancement du jeu.

        Le processus renait avant que libthieves.so soit chargee : l'agent
        refuse alors de demarrer en nommant les symboles absents, ce qui est
        le bon comportement mais pas le bon moment. On detache entre deux
        essais, sans quoi la session a moitie ouverte fuirait.
        """
        derniere: Exception | None = None
        # Hors de la boucle : un frida discordant ne se repare pas en
        # attendant, inutile de le constater quinze fois.
        self.verifier_frida()
        for _ in range(essais):
            try:
                self.attach()
                return
            except (SessionError, DeviceError, frida.ProcessNotFoundError,
                    frida.TransportError, frida.ServerNotRunningError) as exc:
                derniere = exc
                self.detach()
                dormir(delai)
        raise SessionError(
            f"attache impossible apres {essais} essais. Derniere erreur : "
            f"{derniere}"
        )

    HEARTBEAT_SECONDS = 2.0

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(self.HEARTBEAT_SECONDS):
            try:
                self.script.exports_sync.heartbeat()
            except Exception:
                # Session fermee ou jeu disparu : le fil s'arrete de lui-meme.
                return

    def _start_heartbeat(self) -> None:
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="kot-heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()

    @staticmethod
    def _on_message(message: dict, data: bytes | None) -> None:
        if message["type"] == "error":
            print("[agent] ERREUR:", message.get("stack", message))
        else:
            print("[agent]", message.get("payload"))

    @property
    def api(self):
        if self.script is None:
            raise SessionError("session non attachee")
        return self.script.exports_sync

    def detach(self) -> None:
        self._heartbeat_stop.set()
        if self.session is not None:
            self.session.detach()
            self.session = None
            self.script = None
