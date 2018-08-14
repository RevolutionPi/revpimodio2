# -*- coding: utf-8 -*-
"""RevPiModIO Helperklassen und Tools."""
__author__ = "Sven Sager"
__copyright__ = "Copyright (C) 2018 Sven Sager"
__license__ = "LGPLv3"

import queue
import warnings
from math import ceil
from threading import Event, Lock, Thread
from timeit import default_timer
from revpimodio2 import RISING, FALLING, BOTH


class EventCallback(Thread):

    """Thread fuer das interne Aufrufen von Event-Funktionen.

    Der Eventfunktion, welche dieser Thread aufruft, wird der Thread selber
    als Parameter uebergeben. Darauf muss bei der definition der Funktion
    geachtet werden z.B. "def event(th):". Bei umfangreichen Funktionen kann
    dieser ausgewertet werden um z.B. doppeltes Starten zu verhindern.
    Ueber EventCallback.ioname kann der Name des IO-Objekts abgerufen werden,
    welches das Event ausgeloest hast. EventCallback.iovalue gibt den Wert des
    IO-Objekts zum Ausloesezeitpunkt zurueck.
    Der Thread stellt das EventCallback.exit Event als Abbruchbedingung fuer
    die aufgerufene Funktion zur Verfuegung.
    Durch Aufruf der Funktion EventCallback.stop() wird das exit-Event gesetzt
    und kann bei Schleifen zum Abbrechen verwendet werden.
    Mit dem .exit() Event auch eine Wartefunktion realisiert
    werden: "th.exit.wait(0.5)" - Wartet 500ms oder bricht sofort ab, wenn
    fuer den Thread .stop() aufgerufen wird.

    while not th.exit.is_set():
        # IO-Arbeiten
        th.exit.wait(0.5)

    """

    __slots__ = "daemon", "exit", "func", "ioname", "iovalue"

    def __init__(self, func, name, value):
        """Init EventCallback class.

        @param func Funktion die beim Start aufgerufen werden soll
        @param name IO-Name
        @param value IO-Value zum Zeitpunkt des Events

        """
        super().__init__()
        self.daemon = True
        self.exit = Event()
        self.func = func
        self.ioname = name
        self.iovalue = value

    def run(self):
        """Ruft die registrierte Funktion auf."""
        self.func(self)

    def stop(self):
        """Setzt das exit-Event mit dem die Funktion beendet werden kann."""
        self.exit.set()


class Cycletools():

    """Werkzeugkasten fuer Cycleloop-Funktion.

    Diese Klasse enthaelt Werkzeuge fuer Zyklusfunktionen, wie Taktmerker
    und Flankenmerker.
    Zu beachten ist, dass die Flankenmerker beim ersten Zyklus alle den Wert
    True haben! Ueber den Merker Cycletools.first kann ermittelt werden,
    ob es sich um den ersten Zyklus handelt.

    Taktmerker flag1c, flag5c, flag10c, usw. haben den als Zahl angegebenen
    Wert an Zyklen jeweils False und True.
    Beispiel: flag5c hat 5 Zyklen den Wert False und in den naechsten 5 Zyklen
    den Wert True.

    Flankenmerker flank5c, flank10c, usw. haben immer im, als Zahl angebenen
    Zyklus fuer einen Zyklusdurchlauf den Wert True, sonst False.
    Beispiel: flank5c hat immer alle 5 Zyklen den Wert True.

    Diese Merker koennen z.B. verwendet werden um, an Outputs angeschlossene,
    Lampen synchron blinken zu lassen.

    """

    __slots__ = "__cycle", "__cycletime", "__ucycle", \
        "__dict_ton", "__dict_tof", "__dict_tp", "first", \
        "flag1c", "flag5c", "flag10c", "flag15c", "flag20c", \
        "flank5c", "flank10c", "flank15c", "flank20c", "var"

    def __init__(self, cycletime):
        """Init Cycletools class."""
        self.__cycle = 0
        self.__cycletime = cycletime
        self.__ucycle = 0
        self.__dict_ton = {}
        self.__dict_tof = {}
        self.__dict_tp = {}

        # Taktmerker
        self.first = True
        self.flag1c = False
        self.flag5c = False
        self.flag10c = False
        self.flag15c = False
        self.flag20c = False

        # Flankenmerker
        self.flank5c = True
        self.flank10c = True
        self.flank15c = True
        self.flank20c = True

        # Benutzerdaten
        class Var:
            pass
        self.var = Var()

    def _docycle(self):
        """Zyklusarbeiten."""
        # Einschaltverzoegerung
        for tof in self.__dict_tof:
            if self.__dict_tof[tof] > 0:
                self.__dict_tof[tof] -= 1

        # Ausschaltverzoegerung
        for ton in self.__dict_ton:
            if self.__dict_ton[ton][1]:
                if self.__dict_ton[ton][0] > 0:
                    self.__dict_ton[ton][0] -= 1
                self.__dict_ton[ton][1] = False
            else:
                self.__dict_ton[ton][0] = -1

        # Impuls
        for tp in self.__dict_tp:
            if self.__dict_tp[tp][1]:
                if self.__dict_tp[tp][0] > 0:
                    self.__dict_tp[tp][0] -= 1
                else:
                    self.__dict_tp[tp][1] = False
            else:
                self.__dict_tp[tp][0] = -1

        # Flankenmerker
        self.flank5c = False
        self.flank10c = False
        self.flank15c = False
        self.flank20c = False

        # Logische Flags
        self.first = False
        self.flag1c = not self.flag1c

        # Berechnete Flags
        self.__cycle += 1
        if self.__cycle == 5:
            self.__ucycle += 1
            if self.__ucycle == 3:
                self.flank15c = True
                self.flag15c = not self.flag15c
                self.__ucycle = 0
            if self.flag5c:
                if self.flag10c:
                    self.flank20c = True
                    self.flag20c = not self.flag20c
                self.flank10c = True
                self.flag10c = not self.flag10c
            self.flank5c = True
            self.flag5c = not self.flag5c
            self.__cycle = 0

    def get_tof(self, name):
        """Wert der Ausschaltverzoegerung.
        @param name Eindeutiger Name des Timers
        @return Wert <class 'bool'> der Ausschaltverzoegerung"""
        return self.__dict_tof.get(name, 0) > 0

    def get_tofc(self, name):
        """Wert der Ausschaltverzoegerung.
        @param name Eindeutiger Name des Timers
        @return Wert <class 'bool'> der Ausschaltverzoegerung"""
        return self.__dict_tof.get(name, 0) > 0

    def set_tof(self, name, milliseconds):
        """Startet bei Aufruf einen ausschaltverzoegerten Timer.

        @param name Eindeutiger Name fuer Zugriff auf Timer
        @param milliseconds Verzoegerung in Millisekunden

        """
        self.__dict_tof[name] = ceil(milliseconds / self.__cycletime)

    def set_tofc(self, name, cycles):
        """Startet bei Aufruf einen ausschaltverzoegerten Timer.

        @param name Eindeutiger Name fuer Zugriff auf Timer
        @param cycles Zyklusanzahl, der Verzoegerung wenn nicht neu gestartet

        """
        self.__dict_tof[name] = cycles

    def get_ton(self, name):
        """Einschaltverzoegerung.
        @param name Eindeutiger Name des Timers
        @return Wert <class 'bool'> der Einschaltverzoegerung"""
        return self.__dict_ton.get(name, [-1])[0] == 0

    def get_tonc(self, name):
        """Einschaltverzoegerung.
        @param name Eindeutiger Name des Timers
        @return Wert <class 'bool'> der Einschaltverzoegerung"""
        return self.__dict_ton.get(name, [-1])[0] == 0

    def set_ton(self, name, milliseconds):
        """Startet einen einschaltverzoegerten Timer.

        @param name Eindeutiger Name fuer Zugriff auf Timer
        @param milliseconds Millisekunden, der Verzoegerung wenn neu gestartet

        """
        if self.__dict_ton.get(name, [-1])[0] == -1:
            self.__dict_ton[name] = \
                [ceil(milliseconds / self.__cycletime), True]
        else:
            self.__dict_ton[name][1] = True

    def set_tonc(self, name, cycles):
        """Startet einen einschaltverzoegerten Timer.

        @param name Eindeutiger Name fuer Zugriff auf Timer
        @param cycles Zyklusanzahl, der Verzoegerung wenn neu gestartet

        """
        if self.__dict_ton.get(name, [-1])[0] == -1:
            self.__dict_ton[name] = [cycles, True]
        else:
            self.__dict_ton[name][1] = True

    def get_tp(self, name):
        """Impulstimer.
        @param name Eindeutiger Name des Timers
        @return Wert <class 'bool'> des Impulses"""
        return self.__dict_tp.get(name, [-1])[0] > 0

    def get_tpc(self, name):
        """Impulstimer.
        @param name Eindeutiger Name des Timers
        @return Wert <class 'bool'> des Impulses"""
        return self.__dict_tp.get(name, [-1])[0] > 0

    def set_tp(self, name, milliseconds):
        """Startet einen Impuls Timer.

        @param name Eindeutiger Name fuer Zugriff auf Timer
        @param milliseconds Millisekunden, die der Impuls anstehen soll

        """
        if self.__dict_tp.get(name, [-1])[0] == -1:
            self.__dict_tp[name] = \
                [ceil(milliseconds / self.__cycletime), True]
        else:
            self.__dict_tp[name][1] = True

    def set_tpc(self, name, cycles):
        """Startet einen Impuls Timer.

        @param name Eindeutiger Name fuer Zugriff auf Timer
        @param cycles Zyklusanzahl, die der Impuls anstehen soll

        """
        if self.__dict_tp.get(name, [-1])[0] == -1:
            self.__dict_tp[name] = [cycles, True]
        else:
            self.__dict_tp[name][1] = True


class ProcimgWriter(Thread):

    """Klasse fuer Synchroniseriungs-Thread.

    Diese Klasse wird als Thread gestartet, wenn das Prozessabbild zyklisch
    synchronisiert werden soll. Diese Funktion wird hauptsaechlich fuer das
    Event-Handling verwendet.

    """

    __slots__ = "__dict_delay", "__eventth", "__eventqth", "__eventwork", \
        "_adjwait", "_eventq", "_ioerror", "_maxioerrors", "_modio", \
        "_refresh", "_work", "daemon", "lck_refresh", "newdata"

    def __init__(self, parentmodio):
        """Init ProcimgWriter class.
        @param parentmodio Parent Object"""
        super().__init__()
        self.__dict_delay = {}
        self.__eventth = Thread(target=self.__exec_th)
        self.__eventqth = queue.Queue()
        self.__eventwork = False
        self._adjwait = 0
        self._eventq = queue.Queue()
        self._ioerror = 0
        self._maxioerrors = 0
        self._modio = parentmodio
        self._refresh = 0.05
        self._work = Event()

        self.daemon = True
        self.lck_refresh = Lock()
        self.newdata = Event()

    def __check_change(self, dev):
        """Findet Aenderungen fuer die Eventueberwachung."""
        for io_event in dev._dict_events:

            if dev._ba_datacp[io_event._slc_address] == \
                    dev._ba_devdata[io_event._slc_address]:
                continue

            if io_event._bitaddress >= 0:
                boolcp = bool(int.from_bytes(
                    dev._ba_datacp[io_event._slc_address],
                    byteorder=io_event._byteorder
                ) & 1 << io_event._bitaddress)
                boolor = bool(int.from_bytes(
                    dev._ba_devdata[io_event._slc_address],
                    byteorder=io_event._byteorder
                ) & 1 << io_event._bitaddress)

                if boolor == boolcp:
                    continue

                for regfunc in dev._dict_events[io_event]:
                    if regfunc.edge == BOTH \
                            or regfunc.edge == RISING and boolor \
                            or regfunc.edge == FALLING and not boolor:
                        if regfunc.delay == 0:
                            if regfunc.as_thread:
                                self.__eventqth.put(
                                    (regfunc, io_event._name, io_event.value),
                                    False
                                )
                            else:
                                self._eventq.put(
                                    (regfunc, io_event._name, io_event.value),
                                    False
                                )
                        else:
                            # Verzögertes Event in dict einfügen
                            tupfire = (
                                regfunc, io_event._name, io_event.value
                            )
                            if regfunc.overwrite \
                                    or tupfire not in self.__dict_delay:
                                self.__dict_delay[tupfire] = ceil(
                                    regfunc.delay / 1000 / self._refresh
                                )
            else:
                for regfunc in dev._dict_events[io_event]:
                    if regfunc.delay == 0:
                        if regfunc.as_thread:
                            self.__eventqth.put(
                                (regfunc, io_event._name, io_event.value),
                                False
                            )
                        else:
                            self._eventq.put(
                                (regfunc, io_event._name, io_event.value),
                                False
                            )
                    else:
                        # Verzögertes Event in dict einfügen
                        tupfire = (
                            regfunc, io_event._name, io_event.value
                        )
                        if regfunc.overwrite \
                                or tupfire not in self.__dict_delay:
                            self.__dict_delay[tupfire] = ceil(
                                regfunc.delay / 1000 / self._refresh
                            )

        # Nach Verarbeitung aller IOs die Bytes kopieren (Lock ist noch drauf)
        dev._ba_datacp = dev._ba_devdata[:]

    def __exec_th(self):
        """Laeuft als Thread, der Events als Thread startet."""
        while self.__eventwork:
            try:
                tup_fireth = self.__eventqth.get(timeout=1)
                th = EventCallback(
                    tup_fireth[0].func, tup_fireth[1], tup_fireth[2]
                )
                th.start()
            except queue.Empty:
                pass

    def _collect_events(self, value):
        """Aktiviert oder Deaktiviert die Eventueberwachung.
        @param value True aktiviert / False deaktiviert
        @return True, wenn Anforderung erfolgreich war"""
        if type(value) != bool:
            raise ValueError("value must be <class 'bool'>")

        # Nur starten, wenn System läuft
        if not self.is_alive():
            self.__eventwork = False
            return False

        if self.__eventwork != value:
            with self.lck_refresh:
                self.__eventwork = value
                self.__eventqth = queue.Queue()
                self._eventq = queue.Queue()
                self.__dict_delay = {}

            # Threadmanagement
            if value and not self.__eventth.is_alive():
                self.__eventth = Thread(target=self.__exec_th)
                self.__eventth.daemon = True
                self.__eventth.start()

        return True

    def _get_ioerrors(self):
        """Ruft aktuelle Anzahl der Fehler ab.
        @return Aktuelle Fehleranzahl"""
        return self._ioerror

    def _gotioerror(self):
        """IOError Verwaltung fuer autorefresh."""
        self._ioerror += 1
        if self._maxioerrors != 0 and self._ioerror >= self._maxioerrors:
            raise RuntimeError(
                "reach max io error count {0} on process image".format(
                    self._maxioerrors
                )
            )
        warnings.warn(
            "count {0} io errors on process image".format(self._ioerror),
            RuntimeWarning
        )

    def get_maxioerrors(self):
        """Gibt die Anzahl der maximal erlaubten Fehler zurueck.
        @return Anzahl erlaubte Fehler"""
        return self._maxioerrors

    def get_refresh(self):
        """Gibt Zykluszeit zurueck.
        @return <class 'int'> Zykluszeit in Millisekunden"""
        return int(self._refresh * 1000)

    def run(self):
        """Startet die automatische Prozessabbildsynchronisierung."""
        fh = self._modio._create_myfh()
        self._adjwait = self._refresh

        while not self._work.is_set():
            ot = default_timer()

            # Lockobjekt holen und Fehler werfen, wenn nicht schnell genug
            if not self.lck_refresh.acquire(timeout=self._adjwait):
                warnings.warn(
                    "cycle time of {0} ms exceeded on lock".format(
                        int(self._refresh * 1000)
                    ),
                    RuntimeWarning
                )
                # Verzögerte Events pausieren an dieser Stelle
                continue

            try:
                fh.seek(0)
                bytesbuff = bytearray(fh.read(self._modio._length))

                if self._modio._monitoring:
                    # Inputs und Outputs in Puffer
                    for dev in self._modio._lst_refresh:
                        with dev._filelock:
                            dev._ba_devdata[:] = bytesbuff[dev._slc_devoff]
                            if self.__eventwork \
                                    and len(dev._dict_events) > 0 \
                                    and dev._ba_datacp != dev._ba_devdata:
                                self.__check_change(dev)

                else:
                    # Inputs in Puffer, Outputs in Prozessabbild
                    for dev in self._modio._lst_refresh:
                        with dev._filelock:
                            dev._ba_devdata[dev._slc_inp] = \
                                bytesbuff[dev._slc_inpoff]
                            if self.__eventwork\
                                    and len(dev._dict_events) > 0 \
                                    and dev._ba_datacp != dev._ba_devdata:
                                self.__check_change(dev)

                            fh.seek(dev._slc_outoff.start)
                            fh.write(dev._ba_devdata[dev._slc_out])

                    if self._modio._buffedwrite:
                        fh.flush()

            except IOError:
                self._gotioerror()
                self.lck_refresh.release()
                continue

            else:
                # Alle aufwecken
                self.lck_refresh.release()
                self.newdata.set()

            finally:
                # Verzögerte Events prüfen
                if self.__eventwork:
                    for tup_fire in tuple(self.__dict_delay.keys()):
                        if tup_fire[0].overwrite and \
                                getattr(self._modio.io, tup_fire[1]).value != \
                                tup_fire[2]:
                            del self.__dict_delay[tup_fire]
                        else:
                            self.__dict_delay[tup_fire] -= 1
                            if self.__dict_delay[tup_fire] <= 0:
                                # Verzögertes Event übernehmen und löschen
                                if tup_fire[0].as_thread:
                                    self.__eventqth.put(tup_fire, False)
                                else:
                                    self._eventq.put(tup_fire, False)
                                del self.__dict_delay[tup_fire]

                # Refresh abwarten
                self._work.wait(self._adjwait)

            # Wartezeit anpassen um echte self._refresh zu erreichen
            if default_timer() - ot >= self._refresh:
                self._adjwait -= 0.001
                if self._adjwait < 0:
                    warnings.warn(
                        "cycle time of {0} ms exceeded".format(
                            int(self._refresh * 1000)
                        ),
                        RuntimeWarning
                    )
                    self._adjwait = 0
            else:
                self._adjwait += 0.001

        # Alle am Ende erneut aufwecken
        self._collect_events(False)
        self.newdata.set()
        fh.close()

    def stop(self):
        """Beendet die automatische Prozessabbildsynchronisierung."""
        self._collect_events(False)
        self._work.set()

    def set_maxioerrors(self, value):
        """Setzt die Anzahl der maximal erlaubten Fehler.
        @param value Anzahl erlaubte Fehler"""
        if type(value) == int and value >= 0:
            self._maxioerrors = value
        else:
            raise ValueError("value must be 0 or a positive integer")

    def set_refresh(self, value):
        """Setzt die Zykluszeit in Millisekunden.
        @param value <class 'int'> Millisekunden"""
        if type(value) == int and 10 <= value <= 2000:
            waitdiff = self._refresh - self._adjwait
            self._refresh = value / 1000
            self._adjwait = self._refresh - waitdiff
        else:
            raise ValueError(
                "refresh time must be 10 to 2000 milliseconds"
            )

    ioerrors = property(_get_ioerrors)
    maxioerrors = property(get_maxioerrors, set_maxioerrors)
    refresh = property(get_refresh, set_refresh)
