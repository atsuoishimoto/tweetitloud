# -*- coding: ShiftJIS -*-

import os, ConfigParser, StringIO, webbrowser
from pymfc import app, wnd, traynotify, gdi, menu, layout
from pymfc import shellapi
import tweepy
from synthDrivers import _nvdajp_jtalk
_nvdajp_jtalk.initialize()




class Notify(traynotify.TrayNotify):
    __running = False
    def onRBtnUp(self, msg):
        if self.__running:
            return
        self.__running = True
        try:
            popup = menu.PopupMenu(u"popup")
            popup.append(menu.MenuItem(u"config", u"Config"))
            popup.append(menu.MenuItem(u"quit", u"Quit"))
            popup.create()
            
            msg.wnd.setForegroundWindow()
            pos = msg.wnd.getCursorPos()
            pos =msg.wnd.clientToScreen(pos)
            item = popup.trackPopup(pos, msg.wnd, nonotify=True, returncmd=True)
            if item:
                if item.menuid == u"quit":
                    twilapp.notifyframe.destroy()
                elif item.menuid == u"config":
                    twilapp.showConfig()
        finally:
            self.__running = False
            

def callLater(elapse, f):
    def timer():
        p.unRegister()
        f()
        
    p = wnd.TimerProc(elapse, timer)
    return p
    
class Producer:
    WAIT = 180
    GAP = 1000
    _timer = None
    def __init__(self):
        self._queue = []
        
    def _setTimer(self):
        if self._queue and not self._timer:
            self._timer = callLater(self.GAP, self._produce)
    
    def _produce(self):
        self._timer = None
        if not self._queue:
            return
        msg = self._queue.pop(0)
        _nvdajp_jtalk.speak(msg.text)
        wait = len(msg.text)*self.WAIT
        
        self._timer = callLater(wait+self.GAP, self._produce_finished)
    
    def _produce_finished(self):
        self._timer = None
        _nvdajp_jtalk.stop()
        self._produce()
        
    def submit(self, timeline):
        self._queue.extend(timeline)
        if not self._timer:
            self._setTimer()


class TWILApp:
    APPNAME = u"TweetItLoud"
    ICON_APP = gdi.Icon(filename=u"twil.ico", cx=16, cy=16)

    CONFIG = """
[CONFIG]
consumer_key = 
consumer_secret = 
access_token = 
access_secret = 
"""

    CONFIGFILEPATH = os.path.join(
        shellapi.shGetSpecialFolderPath(None, shellapi.CSIDL.appdata, create=False),
        APPNAME
        )
    CONFIGFILENAME = os.path.join(CONFIGFILEPATH, u'tweetitloud.config')
    
    ELAPSE = 20000
    MAX_TIMELINE = 50
    api = None
    _seen = 0
    _running = False
    _connected = False
    
    def __init__(self):
        self.__readconfig()
        self._producer = Producer()
        
    def __readconfig(self):
        config = self.__loadconfig()
        self.consumer_key = config.get('CONFIG', 'consumer_key')
        self.consumer_secret = config.get('CONFIG', 'consumer_secret')
        self.access_token = config.get('CONFIG', 'access_token')
        self.access_secret = config.get('CONFIG', 'access_secret')
        
    def __loadconfig(self):
        config = ConfigParser.SafeConfigParser()
        config.readfp(StringIO.StringIO(self.CONFIG))
        
        if os.path.exists(self.CONFIGFILENAME):
            try:
                config.read(self.CONFIGFILENAME)
            except:
                # ignore errors
                pass
        return config
    
    def __saveconfig(self):
        config = self.__loadconfig()
        config.set('CONFIG', 'consumer_key', self.consumer_key.encode('ascii'))
        config.set('CONFIG', 'consumer_secret', self.consumer_secret.encode('ascii'))
        config.set('CONFIG', 'access_token', self.access_token.encode('ascii'))
        config.set('CONFIG', 'access_secret', self.access_secret.encode('ascii'))

        
        if not os.path.exists(self.CONFIGFILEPATH):
            os.makedirs(self.CONFIGFILEPATH)
        with open(self.CONFIGFILENAME, 'w') as f:
            config.write(f)
        
    def showConfig(self):
        ret = ConfigDialog().doModal()
        if ret:
            self.api = None
            self.__saveconfig()
            return True

    def run(self):
        self.notifyframe = wnd.FrameWnd(style=wnd.FrameWnd.STYLE(visible=False))
        self.notify = Notify(self.notifyframe, self.ICON_APP, self.APPNAME)
        self.notifyframe.create()
        
        if not self.consumer_key or not self.consumer_secret or not self.access_token or not self.access_secret:
            self.showConfig()

        p = wnd.TimerProc(self.ELAPSE, self._read)
        app.run()

    def login(self):
        if self.consumer_key and self.consumer_secret and self.access_token and self.access_secret:
            auth = tweepy.OAuthHandler(self.consumer_key, self.consumer_secret)
            auth.set_access_token(self.access_token, self.access_secret)
            self.api = tweepy.API(auth)
        
    def _fetch(self, n):
        try:
            if not self.api:    
                self.login()
            if not self.api:    
                return
            timeline = self.api.home_timeline(n)
            timeline = [tw for tw in timeline[::-1] if tw.id > self._seen]
            if timeline:
                self._seen = max(self._seen, max(tw.id for tw in timeline))
            
        except Exception, e:
            self.api = None
            self.notify.setIcon(tip=unicode(str(e), "mbcs"))
            return []
        else:
            self.notify.setIcon(tip=self.APPNAME)
            self._connected = True
            
        return timeline
            
    def _read(self):
        if self._running:
            return
        self._running = True
        try:
            firsttime = not self._connected
            timeline = self._fetch(self.MAX_TIMELINE)
            if not firsttime:
                self._producer.submit(timeline)
        finally:
            self._running = False



class _PINDialog(wnd.Dialog):
    TITLE = TWILApp.APPNAME
    FONT = gdi.Font(face=u"MS UI Gothic", point=10)

    def _prepare(self, kwargs):
        super(_PINDialog, self)._prepare(kwargs)
        
        self._layout = layout.Table(parent=self, font=self.FONT, adjustparent=True,
            pos=(10,5), margin_bottom=5, margin_right=10, rowgap=5)

        row = self._layout.addRow()
        cell = row.addCell()
        cell.add(u"暗証番号")
        cell.add(None)

        cell = row.addCell()
        cell.add(wnd.Edit, width=80, name="code")

        row = self._layout.addRow()
        cell = row.addCell(colspan=2, alignright=True)

        cell.add(wnd.OkButton, title=u"OK", name='ok')
        cell.add(None)
        cell.add(wnd.CancelButton, title=u"Cancel", name='cancel')

        self.setDefaultValue(None)

    def onOk(self, msg=None):
        v = self._layout.ctrls.code.getText().strip()
        if not v:
            wnd.msgbox(None, u"値を指定してください", self.TITLE)
            self._layout.ctrls.code.setFocus()
            return
            
        if max(v) >= u'\x80' or min(v) <= u' ':
            wnd.msgbox(None, u"値が正しくありません", self.TITLE)
            self._layout.ctrls.code.setFocus()
            return

        code = v.encode("ascii")

        self.setResultValue(code)
        self.endDialog(self.IDOK)

    def onCancel(self, msg=None):
        self.setResultValue(None)
        self.endDialog(self.IDCANCEL)

    
class ConfigDialog(wnd.Dialog):
    TITLE = TWILApp.APPNAME
    FONT = gdi.Font(face=u"MS UI Gothic", point=10)

    def _prepare(self, kwargs):
        super(ConfigDialog, self)._prepare(kwargs)
        
        self._layout = layout.Table(parent=self, font=self.FONT, adjustparent=True,
            pos=(10,5), margin_bottom=5, margin_right=10, rowgap=5)

        row = self._layout.addRow()
        cell = row.addCell()
        cell.add(u"consumer key")
        cell.add(None)

        cell = row.addCell()
        cell.add(wnd.Edit, title=unicode(twilapp.consumer_key, "ascii", errors="replace"), width=80, name="consumer_key")

        row = self._layout.addRow()
        cell = row.addCell()
        cell.add(u"consumer secret")
        cell.add(None)

        cell = row.addCell()
        cell.add(wnd.Edit, title=unicode(twilapp.consumer_secret, "ascii", errors="replace"), width=80, name="consumer_secret")

        row = self._layout.addRow()
        cell = row.addCell(colspan=2)
        item = cell.add(wnd.Button, title=u" アクセストークンを取得 ", name='gettoken')
        item.ctrl.msglistener.CLICKED = self._showAccessToken
        
        row = self._layout.addRow()
        cell = row.addCell()
        cell.add(u"access token")
        cell.add(None)

        cell = row.addCell()
        cell.add(wnd.Edit, title=unicode(twilapp.access_token, "ascii", errors="replace"), width=80, name="access_token")

        row = self._layout.addRow()
        cell = row.addCell()
        cell.add(u"access secret")
        cell.add(None)

        cell = row.addCell()
        cell.add(wnd.Edit, title=unicode(twilapp.access_secret, "ascii", errors="replace"), width=80, name="access_secret")

        row = self._layout.addRow()
        cell = row.addCell(colspan=2, alignright=True)

        cell.add(wnd.OkButton, title=u"OK", name='ok')
        cell.add(None)
        cell.add(wnd.CancelButton, title=u"Cancel", name='cancel')

        self.setDefaultValue(None)
        

    def _showAccessToken(self, msg):
        consumer_key = self._check(self._layout.ctrls.consumer_key)
        if not consumer_key:
            return

        consumer_secret = self._check(self._layout.ctrls.consumer_secret)
        if not consumer_secret:
            return
        
        try:
            auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
            redirect_url = auth.get_authorization_url()
            webbrowser.open(redirect_url)
            
            ret = _PINDialog().doModal()
            if ret:
                auth.get_access_token(ret)
        except Exception, e:
            s = unicode(str(e), "mbcs")
            wnd.msgbox(None, s, self.TITLE)
            return

        self._layout.ctrls.access_token.setText(
                unicode(auth.access_token.key, "ascii"))
        self._layout.ctrls.access_secret.setText(
                unicode(auth.access_token.secret, "ascii"))
            
    def _check(self, cntl):
        v = cntl.getText().strip()
        if not v:
            wnd.msgbox(None, u"値を指定してください", self.TITLE)
            cntl.setFocus()
            return
            
        if max(v) >= u'\x80' or min(v) <= u' ':
            wnd.msgbox(None, u"値が正しくありません", self.TITLE)
            cntl.setFocus()
            return

        return v.encode("ascii")
        
    def onOk(self, msg=None):
        consumer_key = self._check(self._layout.ctrls.consumer_key)
        if not consumer_key:
            return

        consumer_secret = self._check(self._layout.ctrls.consumer_secret)
        if not consumer_secret:
            return

        access_token = self._check(self._layout.ctrls.access_token)
        if not access_token:
            return

        access_secret = self._check(self._layout.ctrls.access_secret)
        if not access_secret:
            return

        twilapp.consumer_key = consumer_key
        twilapp.consumer_secret = consumer_secret
        twilapp.access_token = access_token
        twilapp.access_secret = access_secret

        self.setResultValue(True)
        self.endDialog(self.IDOK)

    def onCancel(self, msg=None):
        self.setResultValue(None)
        self.endDialog(self.IDCANCEL)


def run():
    global twilapp
    twilapp = TWILApp()
    twilapp.run()
    
if __name__ == '__main__':
    run()

