from distutils.core import setup
import py2exe


options = {
    "dll_excludes": ["fbclient.dll", "jvm.dll", "tcl85.dll", "tk85.dll", "MPR.dll", "MSWSOCK.dll", 
        "WINHTTP.dll", "POWRPROF.dll", "API-MS-Win-Core-LocalRegistry-L1-1-0.dll", 
        "API-MS-Win-Core-ProcessThreads-L1-1-0.dll", "API-MS-Win-Security-Base-L1-1-0.dll"],
    "excludes": ["Tkconstants","Tkinter","tcl", "doctest", "setuptools"],
    "compressed":1,
    "optimize":2,
    "xref":1,
}


RT_MANIFEST = 24

class Target:
    MANIFEST = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
<assemblyIdentity
  version="1.0.0.0"
  processorArchitecture="X86"
  name="tweetitloud.exe"
/>
<trustInfo xmlns="urn:schemas-microsoft-com:asm.v2">
  <security>
    <requestedPrivileges>
      <requestedExecutionLevel
        level="asInvoker"
        uiAccess="false"/>
    </requestedPrivileges>
  </security>
</trustInfo>
<description>Pomo Timer</description>
<dependency>
  <dependentAssembly>
    <assemblyIdentity
      type="win32"
      name="Microsoft.Windows.Common-Controls"
      version="6.0.0.0"
      processorArchitecture="X86"
      publicKeyToken="6595b64144ccf1df"
      language="*"
    />
  </dependentAssembly>
</dependency>

<dependency>
  <dependentAssembly>
    <assemblyIdentity type="win32" name="Microsoft.VC90.CRT" version="9.0.30729.4148" processorArchitecture="x86" publicKeyToken="1fc8b3b9a1e18e3b" />
  </dependentAssembly>
</dependency>
</assembly>
"""
    def __init__(self, **kw):
        self.__dict__.update(kw)
        # for the versioninfo resources
        self.script = "tweetitloud.py"
        self.version = "0.0.1"
        self.description = "tweetitloud"
        self.company_name = "Atsuo Ishimoto"
        self.name = "Tweet it loud!"
        self.other_resources = [(RT_MANIFEST, 1, self.MANIFEST)]
        self.icon_resources = [(1, "twil.ico")]


setup(name='tweetitloud',
      version="0.0.1",
      data_files=[
          ('', 
              ['README.TXT', 'COPYING', 'twil.ico']),
      ],
      windows = [Target()],
      options = {'py2exe':options}
)


