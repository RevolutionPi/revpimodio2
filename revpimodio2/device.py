#
# python3-RevPiModIO
#
# Webpage: https://revpimodio.org/
# (c) Sven Sager, License: LGPLv3
#
# -*- coding: utf-8 -*-
"""Modul fuer die Verwaltung der Devices."""
from threading import Lock
from .helper import ProcimgWriter


class DeviceList(object):

    """Basisklasse fuer direkten Zugriff auf Device Objekte."""

    def __init__(self):
        """Init DeviceList class."""
        self.__dict_position = {}

    def __contains__(self, key):
        """Prueft ob Device existiert.
        @param key DeviceName str() / Positionsnummer int()
        @return True, wenn Device vorhanden"""
        if type(key) == int:
            return key in self.__dict_position
        elif type(key) == str:
            return hasattr(self, key)
        else:
            return key in self.__dict_position.values()

    def __delattr__(self, key):
        """Entfernt angegebenes Device.
        @param key Device zum entfernen"""
        dev_del = getattr(self, key)

        # Reinigungsjobs
        dev_del.autorefresh(False)
        for io in dev_del:
            delattr(dev_del._modio.io, io.name)

        del self.__dict_position[dev_del.position]
        object.__delattr__(self, key)

    def __delitem__(self, key):
        """Entfernt Device an angegebener Position.
        @param key Deviceposition zum entfernen"""
        self.__delattr__(self[key].name)

    def __getitem__(self, key):
        """Gibt angegebenes Device zurueck.
        @param key DeviceName str() / Positionsnummer int()
        @return Gefundenes Device()-Objekt"""
        if type(key) == int:
            if key not in self.__dict_position:
                raise KeyError("no device on position {}".format(key))
            return self.__dict_position[key]
        else:
            return getattr(self, key)

    def __iter__(self):
        """Gibt Iterator aller Devices zurueck.
        @return iter() aller Devices"""
        for dev in sorted(self.__dict_position):
            yield self.__dict_position[dev]

    def __len__(self):
        """Gibt Anzahl der Devices zurueck.
        return Anzahl der Devices"""
        return len(self.__dict_position)

    def __setattr__(self, key, value):
        """Setzt Attribute nur wenn Device.
        @param key Attributname
        @param value Attributobjekt"""
        if issubclass(type(value), Device):
            object.__setattr__(self, key, value)
            self.__dict_position[value.position] = value
        elif key == "_DeviceList__dict_position":
            object.__setattr__(self, key, value)


class Device(object):

    """Basisklasse fuer alle Device-Objekte.

    Die Basisfunktionalitaet generiert bei Instantiierung alle IOs und
    erweitert den Prozessabbildpuffer um die benoetigten Bytes. Sie verwaltet
    ihren Prozessabbildpuffer und sorgt fuer die Aktualisierung der IO-Werte.

    """

    def __init__(self, parentmodio, dict_device, simulator=False):
        """Instantiierung der Device()-Klasse.

        @param parent RevpiModIO parent object
        @param dict_device dict() fuer dieses Device aus piCotry Konfiguration
        @param simulator: Laed das Modul als Simulator und vertauscht IOs

        """
        self._modio = parentmodio

        self._dict_events = {}
        self._filelock = Lock()
        self._length = 0
        self._selfupdate = False

        # Wertzuweisung aus dict_device
        self.name = dict_device.pop("name")
        self.offset = int(dict_device.pop("offset"))
        self.position = int(dict_device.pop("position"))
        self.producttype = int(dict_device.pop("productType"))

        # IOM-Objekte erstellen und Adressen in SLCs speichern
        if simulator:
            self._slc_inp = self._buildio(
                dict_device.pop("out"), iomodule.Type.INP)
            self._slc_out = self._buildio(
                dict_device.pop("inp"), iomodule.Type.OUT)
        else:
            self._slc_inp = self._buildio(
                dict_device.pop("inp"), iomodule.Type.INP)
            self._slc_out = self._buildio(
                dict_device.pop("out"), iomodule.Type.OUT)
        self._slc_mem = self._buildio(
            dict_device.pop("mem"), iomodule.Type.MEM
        )

        # SLCs mit offset berechnen
        self._slc_devoff = slice(self.offset, self.offset + self._length)
        self._slc_inpoff = slice(
            self._slc_inp.start + self.offset, self._slc_inp.stop + self.offset
        )
        self._slc_outoff = slice(
            self._slc_out.start + self.offset, self._slc_out.stop + self.offset
        )
        self._slc_memoff = slice(
            self._slc_mem.start + self.offset, self._slc_mem.stop + self.offset
        )

        # Neues bytearray und Kopie für mainloop anlegen
        self._ba_devdata = bytearray(self._length)
        self._ba_datacp = bytearray()

        # Alle restlichen attribute an Klasse anhängen
        self.__dict__.update(dict_device)

        # Spezielle Konfiguration von abgeleiteten Klassen durchführen
        self._devconfigure()

    def __bytes__(self):
        """Gibt alle Daten des Devices als bytes() zurueck.
        @return Devicedaten als bytes()"""
        return bytes(self._ba_devdata)

    def __contains__(self, key):
        """Prueft ob IO auf diesem Device liegt.
        @param key IO-Name str() / IO-Bytenummer int()
        @return True, wenn device vorhanden"""
        if type(key) == str:
            return key in self._modio.io \
                and getattr(self._modio.io, key)._parentdevice == self
        elif type(key) == int:
            if key in self._modio.io:
                for io in self._modio.io[key]:
                    if io is not None and io._parentdevice == self:
                        return True
            return False
        else:
            return key._parentdevice == self

    def __int__(self):
        """Gibt die Positon im RevPi Bus zurueck.
        @return Positionsnummer"""
        return self.position

    def __iter__(self):
        """Gibt Iterator aller IOs zurueck.
        @return iter() aller IOs"""
        for lst_io in self._modio.io[self._slc_devoff]:
            for io in lst_io:
                yield io

    def __len__(self):
        """Gibt Anzahl der Bytes zurueck, die dieses Device belegt.
        @return int()"""
        return self._length

    def __str__(self):
        """Gibt den Namen des Devices zurueck.
        @return Devicename"""
        return self.name

    def _buildio(self, dict_io, iotype):
        """Erstellt aus der piCtory-Liste die IOs fuer dieses Device.

        @param dict_io dict()-Objekt aus piCtory Konfiguration
        @param iotype io.Type() Wert
        @return slice()-Objekt mit Start und Stop Position dieser IOs

        """
        if len(dict_io) <= 0:
            return slice(0, 0)

        int_min, int_max = 4096, 0
        for key in sorted(dict_io, key=lambda x: int(x)):

            # Neuen IO anlegen
            if bool(dict_io[key][7]) or self.producttype == 95:
                # Bei Bitwerten oder Core RevPiIOBase verwenden
                io_new = iomodule.IOBase(
                    self, dict_io[key], iotype, "little", False
                )
            else:
                io_new = iomodule.IntIO(
                    self, dict_io[key],
                    iotype,
                    "little",
                    self.producttype == 103
                )

            # IO registrieren
            self._modio.io._private_register_new_io_object(io_new)

            self._length += io_new._length

            # Kleinste und größte Speicheradresse ermitteln
            if io_new._slc_address.start < int_min:
                int_min = io_new._slc_address.start
            if io_new._slc_address.stop > int_max:
                int_max = io_new._slc_address.stop

        return slice(int_min, int_max)

    def _devconfigure(self):
        """Funktion zum ueberschreiben von abgeleiteten Klassen."""
        pass

    def autorefresh(self, activate=True):
        """Registriert dieses Device fuer die automatische Synchronisierung.
        @param activate Default True fuegt Device zur Synchronisierung hinzu"""
        if activate and self not in self._modio._lst_refresh:

            # Daten bei Aufnahme direkt einlesen!
            self._modio.readprocimg(self)

            # Datenkopie anlegen
            self._filelock.acquire()
            self._ba_datacp = self._ba_devdata[:]
            self._filelock.release()

            self._selfupdate = True
            self._modio._lst_refresh.append(self)

            # Thread starten, wenn er noch nicht läuft
            if not self._modio._imgwriter.is_alive():

                # Alte Einstellungen speichern
                imgmaxioerrors = self._modio._imgwriter.maxioerrors
                imgrefresh = self._modio._imgwriter.refresh

                # ImgWriter mit alten Einstellungen erstellen
                self._modio._imgwriter = ProcimgWriter(self._modio)
                self._modio._imgwriter.maxioerrors = imgmaxioerrors
                self._modio._imgwriter.refresh = imgrefresh
                self._modio._imgwriter.start()

        elif not activate and self in self._modio._lst_refresh:
            # Sicher aus Liste entfernen
            with self._modio._imgwriter.lck_refresh:
                self._modio._lst_refresh.remove(self)
            self._selfupdate = False

            # Beenden, wenn keien Devices mehr in Liste sind
            if len(self._modio._lst_refresh) == 0:
                self._modio._imgwriter.stop()

            # Daten beim Entfernen noch einmal schreiben
            if not self._modio._monitoring:
                self._modio.writeprocimg(self)

    def get_allios(self):
        """Gibt eine Liste aller Inputs und Outputs zurueck, keine MEMs.
        @return list() Input und Output, keine MEMs"""
        lst_return = []
        for lst_io in self._modio.io[
                self._slc_inpoff.start:self._slc_outoff.stop]:
            lst_return += lst_io
        return lst_return

    def get_inputs(self):
        """Gibt eine Liste aller Inputs zurueck.
        @return list() Inputs"""
        lst_return = []
        for lst_io in self._modio.io[self._slc_inpoff]:
            lst_return += lst_io
        return lst_return

    def get_outputs(self):
        """Gibt eine Liste aller Outputs zurueck.
        @return list() Outputs"""
        lst_return = []
        for lst_io in self._modio.io[self._slc_outoff]:
            lst_return += lst_io
        return lst_return

    def get_memmories(self):
        """Gibt eine Liste aller mems zurueck.
        @return list() Mems"""
        lst_return = []
        for lst_io in self._modio.io[self._slc_memoff]:
            lst_return += lst_io
        return lst_return

    def readprocimg(self):
        """Alle Inputs fuer dieses Device vom Prozessabbild einlesen.
        @see revpimodio2.modio#RevPiModIO.readprocimg
        RevPiModIO.readprocimg()"""
        self._modio.readprocimg(self)

    def setdefaultvalues(self):
        """Alle Outputbuffer fuer dieses Device auf default Werte setzen.
        @see revpimodio2.modio#RevPiModIO.setdefaultvalues
        RevPiModIO.setdefaultvalues()"""
        self._modio.setdefaultvalues(self)

    def syncoutputs(self):
        """Lesen aller Outputs im Prozessabbild fuer dieses Device.
        @see revpimodio2.modio#RevPiModIO.syncoutputs
        RevPiModIO.syncoutputs()"""
        self._modio.syncoutputs(self)

    def writeprocimg(self):
        """Schreiben aller Outputs dieses Devices ins Prozessabbild.
        @see revpimodio2.modio#RevPiModIO.writeprocimg
        RevPiModIO.writeprocimg()"""
        self._modio.writeprocimg(self)


class Core(Device):

    """Klasse fuer den RevPi Core.

    Stellt Funktionen fuer die LEDs und den Status zur Verfuegung.

    """

    def _devconfigure(self):
        """Core-Klasse vorbereiten."""
        self._iocycle = None
        self._iotemperatur = None
        self._iofrequency = None
        self._ioerrorcnt = None
        self._ioled = 1
        self._ioerrorlimit1 = None
        self._ioerrorlimit2 = None

        # Eigene IO-Liste aufbauen
        self.__lst_io = [x for x in self.__iter__()]

        int_lenio = len(self.__lst_io)
        if int_lenio == 6:
            # Core 1.1
            self._iocycle = 1
            self._ioerrorcnt = 2
            self._ioled = 3
            self._ioerrorlimit1 = 4
            self._ioerrorlimit2 = 5
        elif int_lenio == 8:
            # core 1.2
            self._iocycle = 1
            self._ioerrorcnt = 2
            self._iotemperatur = 3
            self._iofrequency = 4
            self._ioled = 5
            self._ioerrorlimit1 = 6
            self._ioerrorlimit2 = 7

    def __errorlimit(self, io_id, errorlimit):
        """Verwaltet das Lesen und Schreiben der ErrorLimits.
        @param io_id Index des IOs fuer ErrorLimit
        @return Aktuellen ErrorLimit oder None wenn nicht verfuegbar"""
        if errorlimit is None:
            return None if io_id is None else int.from_bytes(
                self.__lst_io[io_id].get_value(),
                byteorder=self.__lst_io[io_id]._byteorder
            )
        else:
            if 0 <= errorlimit <= 65535:
                self.__lst_io[io_id].set_value(errorlimit.to_bytes(
                    2, byteorder=self.__lst_io[io_id]._byteorder
                ))
            else:
                raise ValueError(
                    "errorlimit value int() must be between 0 and 65535"
                )

    def _get_status(self):
        """Gibt den RevPi Core Status zurueck.
        @return Status als int()"""
        return int.from_bytes(
            self.__lst_io[0].get_value(), byteorder=self.__lst_io[0]._byteorder
        )

    def _get_leda1(self):
        """Gibt den Zustand der LED A1 vom core zurueck.
        @return 0=aus, 1=gruen, 2=rot"""
        int_led = int.from_bytes(
            self.__lst_io[self._ioled].get_value(),
            byteorder=self.__lst_io[self._ioled]._byteorder
        )
        led = int_led & 1
        led += int_led & 2
        return led

    def _get_leda2(self):
        """Gibt den Zustand der LED A2 vom core zurueck.
        @return 0=aus, 1=gruen, 2=rot"""
        int_led = int.from_bytes(
            self.__lst_io[self._ioled].get_value(),
            byteorder=self.__lst_io[self._ioled]._byteorder
        )
        led = 1 if bool(int_led & 4) else 0
        led = led + 2 if bool(int_led & 8) else led
        return led

    def _set_leda1(self, value):
        """Setzt den Zustand der LED A1 vom core.
        @param value 0=aus, 1=gruen, 2=rot"""
        if 0 <= value <= 3:
            int_led = (self._get_leda2() << 2) + value
            self.__lst_io[self._ioled].set_value(int_led.to_bytes(
                length=1, byteorder=self.__lst_io[self._ioled]._byteorder
            ))
        else:
            raise ValueError("led status int() must be between 0 and 3")

    def _set_leda2(self, value):
        """Setzt den Zustand der LED A2 vom core.
        @param value 0=aus, 1=gruen, 2=rot"""
        if 0 <= value <= 3:
            int_led = (value << 2) + self._get_leda1()
            self.__lst_io[self._ioled].set_value(int_led.to_bytes(
                length=1, byteorder=self.__lst_io[self._ioled]._byteorder
            ))
        else:
            raise ValueError("led status int() must be between 0 and 3")

    A1 = property(_get_leda1, _set_leda1)
    A2 = property(_get_leda2, _set_leda2)
    status = property(_get_status)

    @property
    def picontrolrunning(self):
        """Statusbit fuer piControl-Treiber laeuft.
        @return True, wenn Treiber laeuft"""
        return bool(int.from_bytes(
            self.__lst_io[0].get_value(),
            byteorder=self.__lst_io[0]._byteorder
        ) & 1)

    @property
    def unconfdevice(self):
        """Statusbit fuer ein IO-Modul nicht mit PiCtory konfiguriert.
        @return True, wenn IO Modul nicht konfiguriert"""
        return bool(int.from_bytes(
            self.__lst_io[0].get_value(),
            byteorder=self.__lst_io[0]._byteorder
        ) & 2)

    @property
    def missingdeviceorgate(self):
        """Statusbit fuer ein IO-Modul fehlt oder piGate konfiguriert.
        @return True, wenn IO-Modul fehlt oder piGate konfiguriert"""
        return bool(int.from_bytes(
            self.__lst_io[0].get_value(),
            byteorder=self.__lst_io[0]._byteorder
        ) & 4)

    @property
    def overunderflow(self):
        """Statusbit Modul belegt mehr oder weniger Speicher als konfiguriert.
        @return True, wenn falscher Speicher belegt ist"""
        return bool(int.from_bytes(
            self.__lst_io[0].get_value(),
            byteorder=self.__lst_io[0]._byteorder
        ) & 8)

    @property
    def leftgate(self):
        """Statusbit links vom RevPi ist ein piGate Modul angeschlossen.
        @return True, wenn piGate links existiert"""
        return bool(int.from_bytes(
            self.__lst_io[0].get_value(),
            byteorder=self.__lst_io[0]._byteorder
        ) & 16)

    @property
    def rightgate(self):
        """Statusbit rechts vom RevPi ist ein piGate Modul angeschlossen.
        @return True, wenn piGate rechts existiert"""
        return bool(int.from_bytes(
            self.__lst_io[0].get_value(),
            byteorder=self.__lst_io[0]._byteorder
        ) & 32)

    @property
    def iocycle(self):
        """Gibt Zykluszeit der Prozessabbildsynchronisierung zurueck.
        @return Zykluszeit in ms"""
        return None if self._iocycle is None else int.from_bytes(
            self.__lst_io[self._iocycle].get_value(),
            byteorder=self.__lst_io[self._iocycle]._byteorder
        )

    @property
    def temperatur(self):
        """Gibt CPU-Temperatur zurueck.
        @return CPU-Temperatur in Celsius"""
        return None if self._iotemperatur is None else int.from_bytes(
            self.__lst_io[self._iotemperatur].get_value(),
            byteorder=self.__lst_io[self._iotemperatur]._byteorder
        )

    @property
    def frequency(self):
        """Gibt CPU Taktfrequenz zurueck.
        @return CPU Taktfrequenz in MHz"""
        return None if self._iofrequency is None else int.from_bytes(
            self.__lst_io[self._iofrequency].get_value(),
            byteorder=self.__lst_io[self._iofrequency]._byteorder
        ) * 10

    @property
    def ioerrorcount(self):
        """Gibt Fehleranzahl auf RS485 piBridge Bus zurueck.
        @return Fehleranzahl der piBridge"""
        return None if self._ioerrorcnt is None else int.from_bytes(
            self.__lst_io[self._ioerrorcnt].get_value(),
            byteorder=self.__lst_io[self._ioerrorcnt]._byteorder
        )

    @property
    def errorlimit1(self):
        """Gibt RS485 ErrorLimit1 Wert zurueck.
        @return Aktueller Wert fuer ErrorLimit1"""
        return self.__errorlimit(self._ioerrorlimit1, None)

    @errorlimit1.setter
    def errorlimit1(self, value):
        """Setzt RS485 ErrorLimit1 auf neuen Wert.
        @param value Neuer ErrorLimit1 Wert"""
        self.__errorlimit(self._ioerrorlimit1, value)

    @property
    def errorlimit2(self):
        """Gibt RS485 ErrorLimit2 Wert zurueck.
        @return Aktueller Wert fuer ErrorLimit2"""
        return self.__errorlimit(self._ioerrorlimit2, None)

    @errorlimit2.setter
    def errorlimit2(self, value):
        """Setzt RS485 ErrorLimit2 auf neuen Wert.
        @param value Neuer ErrorLimit2 Wert"""
        self.__errorlimit(self._ioerrorlimit2, value)


class Gateway(Device):

    """Klasse fuer die RevPi Gateway-Devices.

    Stellt neben den Funktionen von RevPiDevice weitere Funktionen fuer die
    Gateways bereit. IOs auf diesem Device stellen die replace_io Funktion
    zur verfuegung, ueber die eigene IOs definiert werden, die ein
    RevPiStructIO-Objekt abbilden.
    Dieser IO-Typ kann Werte ueber mehrere Bytes verarbeiten und zurueckgeben.
    @see revpimodio2.io#IOBase.replace_io replace_io(name, frm, **kwargs)

    """

    def __init__(self, parent, dict_device, simulator=False):
        """Erweitert Device-Klasse um get_rawbytes-Funktionen.
        @see #Device.__init__ Device.__init__(...)"""
        super().__init__(parent, dict_device, simulator)

        self._dict_slc = {
            iomodule.Type.INP: self._slc_inp,
            iomodule.Type.OUT: self._slc_out,
            iomodule.Type.MEM: self._slc_mem
        }

    def get_rawbytes(self):
        """Gibt die Bytes aus, die dieses Device verwendet.
        @return bytes() des Devices"""
        return bytes(self._ba_devdata)


class Virtual(Gateway):

    """Klasse fuer die RevPi Virtual-Devices.

    Stellt die selben Funktionen wie Gateway zur Verfuegung. Es koennen
    ueber die reg_*-Funktionen eigene IOs definiert werden, die ein
    RevPiStructIO-Objekt abbilden.
    Dieser IO-Typ kann Werte ueber mehrere Bytes verarbeiten und zurueckgeben.
    @see #Gateway Gateway

    """

    def writeinputdefaults(self):
        """Schreibt fuer ein virtuelles Device piCtory Defaultinputwerte.

        Sollten in piCtory Defaultwerte fuer Inputs eines virtuellen Devices
        angegeben sein, werden diese nur beim Systemstart oder einem piControl
        Reset gesetzt. Sollte danach das Prozessabbild mit NULL ueberschrieben,
        gehen diese Werte verloren.
        Diese Funktion kann nur auf virtuelle Devices angewendet werden!

        @return True, wenn Arbeiten am virtuellen Device erfolgreich waren

        """
        if self._modio._monitoring:
            raise RuntimeError(
                "can not write process image, while system is in monitoring "
                "mode"
            )

        workokay = True
        self._filelock.acquire()

        for io in self.get_inputs():
            self._ba_devdata[io._slc_address] = io.defaultvalue

        # Outpus auf Bus schreiben
        try:
            self._modio._myfh.seek(self._slc_inpoff.start)
            self._modio._myfh.write(self._ba_devdata[self._slc_inp])
            if self._modio._buffedwrite:
                self._modio._myfh.flush()
        except IOError:
            self._modio._gotioerror("write")
            workokay = False

        self._filelock.release()
        return workokay


# Nachträglicher Import
from . import io as iomodule
