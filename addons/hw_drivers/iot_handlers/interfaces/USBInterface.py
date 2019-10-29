from usb import core

from odoo.addons.hw_drivers.controllers.driver import Interface


class USBInterface(Interface):
    connection_type = 'usb'

    def get_devices(self):
        """
        USB devices are identified by a combination of their `idVendor` and
        `idProduct`. We can't be sure this combination in unique per equipment.
        To still allow connecting multiple similar equipments, we complete the
        identifier by a counter. The drawbacks are we can't be sure the equipments
        will get the same identifiers after a reboot or a disconnect/reconnect.
        """
        usb_devices = {}
        devs = core.find(find_all=True)
        cpt = 2
        for dev in devs:
            dev.identifier =  "usb_%04x:%04x" % (dev.idVendor, dev.idProduct)
            if dev.identifier in usb_devices:
                dev.identifier += '_%s' % cpt
                cpt += 1
            usb_devices[dev.identifier] = dev
        return usb_devices
