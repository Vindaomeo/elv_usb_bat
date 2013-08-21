#!/usr/bin/env python

## ELV USB-Bat Terminal Access Class ####################################
# 	                                                   		            #
#                Copyright (C) 2013 Erwin Erkinger                      #
#                     							                        #
# This work by Erwin Erkinger is licensed under                         #
#  a Creative Commons Attribution-ShareAlike 3.0 Unported License.      #
#                                                                      	#
# This program is distributed in the hope that it will be useful,      	#
# but WITHOUT ANY WARRANTY; without even the implied warranty of       	#
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the        	#
# GNU General Public License for more details.                         	#
#                                                                      	#
# You should have received a copy of the GNU General Public License    	#
# with this program.  If not, see <http://www.gnu.org/licenses/>.      	# 
#########################################################################

import usb.core
import usb.util
import sys

class ElvUsbBat:
    def __init__(self, debug=False, timeout=100):
        self.id_vendor=0x18ef
        self.id_product=0xe01a
        self.dbg = debug
        self.dev = None
        self.timeout = timeout

    def attach(self):
        if self.dbg:
            print ""
            print "Looking for device (%x:%x)" % (id_vendor, id_product)
        self.dev = usb.core.find(idVendor=self.id_vendor, idProduct=self.id_product)
        if self.dev is None:
            raise ValueError('Our device is not connected')

        if self.dbg:
            print "Found device on bus %d adr %d !" % (self.dev.bus, self.dev.address)

        try:
            self.dev.set_configuration()
        except usb.core.USBError, info:
            pass  # assume everything is OK
        
        if self.dev.is_kernel_driver_active(0):
            if self.dbg:
                print ""
                print "Try to detach from kernel driver"
            try:
                self.dev.detach_kernel_driver(0)
            except usb.core.USBError as e:
                raise ValueError("Could not detatch kernel driver: %s" % str(e))
            else:
                if self.dbg:
                    print "  ok"

        return self.dev
        
    def print_attrs(self, object,lvl):
        if "__dict__" in dir(object):
            dic = getattr(object,"__dict__")
            keys = dic.keys()
            keys.sort()
            for key in keys:
                print " "*lvl*2,key,"=",dic[key]

    def deep_print(self):
        print "Display values of device:"
        print "-"*30
        
        if self.dev is not None:
            print ""
            self.print_attrs(self.dev,0)
                    
            for cfg in self.dev:
                print "  -------------------"
                self.print_attrs(cfg,1)

                for intf in cfg:
                    print "    -------------------"
                    self.print_attrs(intf,2)

                    for ep in intf:
                        print "      -------------------"
                        self.print_attrs(ep,3)
        else:
            print " Error: No device attached!"

    def write(self, msg):
        wpoint = self.dev[0][(0,0)][1]
        return wpoint.write(msg)

    def send(self, cmd, parameter):
        msg=[0]*3
        msg[0]= 1
        msg[1]= 1+len(parameter)
        msg[2]= cmd
        msg += parameter[:60]
        msg += [0]*(64-len(msg))
        #print "Out:", msg
        return self.write(msg)
        
    def read(self, max_len):
        rpoint = self.dev[0][(0,0)][0]
        return rpoint.read(max_len)

    def clear_read(self):
        ret_val = ""
        try:
            r = self.read(1)
        except:
            r = ""
        while r:
            ret_val+=r
            try:
                r = self.read(1)
            except:
                r = ""
        return ret_val
            
    def get(self):
        msg=[0]*8
        ret_val = {}
        ret_val["Frame_ID"]=0xFF

        try:
            msg = self.read(8)
            #print msg
        except:
            pass
        else:
            if len(msg)==8 and msg[0]==2:
                frame_id = msg[2]
                ret_val["Frame_ID"]=frame_id
                if msg[1]==5 and frame_id==0xF5:
                    key_stat = msg[3]
                    key_slist=[0]*3
                    if key_stat & 0x01:
                        key_slist[0]=1
                    if key_stat & 0x02:
                        key_slist[1]=1
                    if key_stat & 0x04:
                        key_slist[2]=1
                    if key_stat & 0x10:
                        key_slist[0]=2
                    if key_stat & 0x20:
                        key_slist[1]=2
                    if key_stat & 0x40:
                        key_slist[2]=2
                    ret_val["Keys"]=key_slist
                    abs_pos  = msg[4]
                    if abs_pos >127:
                        abs_pos = abs_pos-256
                    ret_val["Abs_Pos"]= abs_pos
                    ret_val["Rel_Pos"]= msg[5]
                    ret_val["Pin_Status"]= msg[6]
                elif msg[1]==3 and frame_id==0xA0:
                    eid = msg[3]
                    if eid == 1:
                        fwv      = msg[4]
                        ret_val["FW_Ver_Major"]=int(fwv/0x10)
                        ret_val["FW_Ver_Minor"]=int(fwv&0x0F)
                    ret_val["Error_ID"] = eid
        
        return ret_val

    def read_firmware(self):
        msg=[]
        fw_ver_major = 15
        fw_ver_minor = 15
        error_id     = 0xFF

        self.send(0xF0,[])
        wait4ret = True
        while(wait4ret):
            r = self.get()
            frame_id = r["Frame_ID"]
            if frame_id == 0xA0:
                error_id = r["Error_ID"]
                fw_ver_major = r["FW_Ver_Major"]
                fw_ver_minor = r["FW_Ver_Minor"]
            elif frame_id == 0xF5:
                #print "Datajunk"
                pass # normal dataframe
            else:
                wait4ret = False
        return (error_id, fw_ver_major, fw_ver_minor)

    def status(self):
        wait4ret = True
        error_id = 0xFF
        while wait4ret:
            r = self.get()
            frame_id = r["Frame_ID"]
            if frame_id == 0xA0 or frame_id == 0xFF:
                if r.has_key("Error_ID"):
                    error_id = r["Error_ID"]
                wait4ret = False
        return error_id

    def light_on(self, time_10msec):
        msg=[int(time_10msec)&0xFF]
        self.send(0xF1, msg)
        return self.status()

    def light_off(self):
        self.send(0xF2, [0])
        return self.status()

    def beep_on(self, time_10msec):
        msg=[int(time_10msec)&0xFF]
        self.send(0xF3, msg)
        return self.status()

    def beep_off(self):
        self.send(0xF4, [])
        return self.status()
        
    def light_auto(self):
        self.send(0xF2, [1])
        return self.status()

    def reset(self):
        self.send(0xF8, [])
        return self.status()

    def reset_pos(self):
        self.send(0xF6, [])
        return self.status()

    def clear_disp(self):
        self.send(0xD9, [])
        return self.status()

    def init_disp(self):
        self.send(0xDC, [])
        return self.status()

    def clear_line(self, line):
        msg=[int(line)&0x03]
        self.send(0xDB, msg)
        return self.status()

    def xprint(self, row, col, text, fine=False):
        msg=[]
        x = (row&0xF)*0x10
        if fine:
            x +=1
        msg.append(x)
        if col>19:
            col = 19
        msg.append(col)
        for c in text[:20]:
            msg.append(ord(c))
        msg += [0]*(23-len(msg))
        self.send(0xD8,msg)
        return self.status()
       
if __name__ == "__main__":

    print "Simple ELV USB-Bat access"
    print "-"*25
    print "Attach device:"
    print "-"*10
    
    device = ElvUsbBat(timeout=10)
    device.attach()
    
    if device.dev is not None:
        print " ok"
        device.clear_read() # get rid of data-junk still in reception  
    
    print "Do tests:"
    print "-"*10

    device.light_on(0)
    device.clear_disp()
    device.xprint(0, 0, "Test")
    device.reset_pos()
    device.clear_line(0)

    x,maj, min = device.read_firmware()
    print "FW_Ver: %d.%d" % (maj,min)
    
    print ""
    print "Leaving with testpattern on display"
    
    device.beep_on(5)
    device.beep_off()

    for i in range(0,4,1):
        msg = "Zeile %d 901234567890" % (i+1)
        device.xprint(i, i, msg, fine=True)
    
    device.light_off()
    device.light_auto()
