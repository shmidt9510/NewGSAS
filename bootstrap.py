#!/usr/bin/env python
# Installs GSAS-II from network using subversion and creates platform-specific
# shortcuts.
# works for Mac & Linux; Windows being tested. 
import os, stat, sys, platform, subprocess
home = 'https://subversion.xray.aps.anl.gov/pyGSAS/'
print 70*'*'
#testing for incorrect locale code'
try:
    import locale
    locale.getdefaultlocale()
except ValueError:
    print 'Your location is not set properly. This causes problems for matplotlib'
    print '  (see https://github.com/matplotlib/matplotlib/issues/5420.)'
    print 'Will try to bypass problem by setting LC_ALL to en_US.UTF-8 (US English)'
    os.environ['LC_ALL'] = 'en_US.UTF-8'
    locale.getdefaultlocale()
print 'Preloading matplotlib to build fonts...'
try:
    import matplotlib
except:
    pass
print 'Checking python packages...',
missing = []
for pkg in ['numpy','scipy','matplotlib','wx',]:
    try:
        exec('import '+pkg)
    except:
        missing.append(pkg)

if missing:
    print """Sorry, this version of Python cannot be used
for GSAS-II. It is missing the following package(s):
\t""",
    for pkg in missing: print " ",pkg,
    print 
    print "This should not happen as this script should be called with a "
    print "specially configured version of the free Anaconda python package."
    print "Please contact Brian Toby (toby@anl.gov)"
    for pkg in ['numpy','scipy','matplotlib','wx',]:
        exec('import '+pkg)
    sys.exit()
try:
    import OpenGL
except:
    print "Missing the OpenGL Python package." 
    print "This should not happen as this script should be called with a "
    print "specially configured version of the free Anaconda python package,"
    print "but GSAS-II can install this package anyway." 
    print "Please contact Brian Toby (toby@anl.gov) to report this problem."

# path to where this script is located
gsaspath = os.path.split(sys.argv[0])[0]
if not gsaspath: gsaspath = os.path.curdir
gsaspath = os.path.abspath(os.path.expanduser(gsaspath))

print '\nChecking for subversion...',
if sys.platform.startswith('win'):
    pathlist = os.environ['PATH'].split(';')
    if os.path.exists(os.path.join(gsaspath,'svn')):
        pathlist.append(os.path.join(gsaspath,'svn','bin'))
else:
    pathlist = os.environ['PATH'].split(':')
    # add the standard location for wandisco svn to the path
    pathlist.append('/opt/subversion/bin')
if sys.platform.startswith('win'):
    svn = 'svn.exe'
else:
    svn = 'svn'
# use svn installed via conda 1st (mac)
if os.path.exists(os.path.join(os.path.split(sys.executable)[0],svn)):
    pathlist.insert(0,os.path.split(sys.executable)[0])
# use svn installed via conda 1st (Windows)
if os.path.exists(os.path.join(os.path.split(sys.executable)[0],'Library','bin',svn)):
    pathlist.insert(0,os.path.join(os.path.split(sys.executable)[0],'Library','bin'))

for path in pathlist:
    svn = os.path.join(path,'svn')
    try:
        p = subprocess.Popen([svn,'help'],stdout=subprocess.PIPE)
        res = p.stdout.read()
        p.communicate()
        break
    except:
        pass
else:
    raise Exception('Subversion (svn) not found')
print ' found svn image: '+svn

print 'Ready to bootstrap GSAS-II from repository\n\t',home,'\nto '+gsaspath
proxycmds = []
if os.path.exists("proxyinfo.txt"):
    fp = open("proxyinfo.txt",'r')
    os.remove("proxyinfo.txt")
print(70*"=")
ans = raw_input("Enter the proxy address [none needed]: ")
if ans.strip() != "":
    proxycmds.append('--config-option')
    proxycmds.append('servers:global:http-proxy-host='+ans.strip())
    fp = open("proxyinfo.txt",'w')
    fp.write(ans.strip()+'\n')
    ans = raw_input("Enter the proxy port [8080]: ")
    if ans.strip() == "": ans="8080"
    proxycmds.append('--config-option')
    proxycmds.append('servers:global:http-proxy-port='+ans.strip())
    fp.write(ans.strip()+'\n')
    fp.close()

print 'Determining system type...',
if sys.platform.startswith('linux'):
    #if platform.processor().find('86') <= -1:
    #    ans = raw_input("Note, GSAS requires an Intel-compatible processor and 32-bit"
    #                    "libraries.\nAre you sure want to continue? [Yes]/no: ")
    #    if ans.lower().find('no') > -1: sys.exit()
    repos = 'linux'
    print 'Linux, assuming Intel-compatible'
elif sys.platform == "darwin" and platform.processor() == 'i386':
    repos = 'osxi86'
    print 'Mac OS X, Intel-compatible'
elif sys.platform == "darwin":
    repos = 'osxppc'
    print 'Mac OS X, PowerPC -- you will need to run scons on fsource files'
elif sys.platform.startswith('win'):
    repos = 'win'
    print 'Windows'
else:
    print 'Unidentifed platform -- you probably will need to run scons to compile the fsource files'

cmd = [svn, 'co', home+ 'trunk/', gsaspath, '--non-interactive', '--trust-server-cert']
if proxycmds: cmd += proxycmds
msg = 'loading GSAS-II'
    
print 70*'*'
print msg + ' from ' + cmd[2]
print 'svn load command:'
for item in cmd: print item,
print ""
p = subprocess.call(cmd)
if p:
    print 'subversion returned an error; Retrying with command for older version...'
    cmd = [svn, 'co', home+ 'trunk/', gsaspath]
    if proxycmds: cmd += proxycmds
    for item in cmd: print item,
    print ""
    p = subprocess.call(cmd)

#===========================================================================
# import all .py files so that .pyc files get created
print 'Byte-compiling all .py files...',
import compileall
compileall.compile_dir(gsaspath,quiet=True)
print 'done'
#===========================================================================
# platform-dependent stuff
#===========================================================================
# on Windows, 
if sys.platform.startswith('win') and os.path.exists(
    os.path.join(gsaspath,"makeBat.py")):
    execfile(os.path.join(gsaspath,"makeBat.py"))
#===========================================================================
# on a Mac, make an applescript 
elif sys.platform.startswith('darwin') and os.path.exists(
    os.path.join(gsaspath,"makeMacApp.py")):
    print('running '+os.path.join(gsaspath,"makeMacApp.py"))
    execfile(os.path.join(gsaspath,"makeMacApp.py"))
#===========================================================================
# On linux, make desktop icon
elif sys.platform.startswith('linux'):
    desktop_template = """
[Desktop Entry]
Encoding=UTF-8
Version=1.0
Type=Application
Terminal=false
Exec=xterm -hold -e %s
Name=GSAS-II
Icon=%s
"""
    loc = '~/Desktop/'
    eloc = os.path.expanduser(loc)
    dfile = os.path.join(eloc,'GSASII.desktop')
    icon = os.path.join(gsaspath, 'gsas2.png')
    script = os.path.join(gsaspath, 'GSASII.py')
    os.chmod(script, # make the .py file executable and readable
             stat.S_IXUSR | stat.S_IRUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IXOTH)
    if os.path.exists(eloc):
        open(dfile,'w').write(desktop_template % (script,icon))
        os.chmod(
            dfile,
            stat.S_IWUSR | stat.S_IXUSR | stat.S_IRUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IXOTH)
	print("created GNOME desktop shortcut "+dfile) 

