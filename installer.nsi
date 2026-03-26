; ═══════════════════════════════════════════════════════════════════
; Echelon Windows Installer — Clean rebuild, no custom functions
; ═══════════════════════════════════════════════════════════════════

Unicode True
SetCompressor /SOLID lzma

!define APP_NAME        "Echelon"
!define APP_VERSION     "2.0.0"
!define APP_PUBLISHER   "Zero"
!define APP_EXE         "Echelon.exe"
!define INSTALL_DIR     "$PROGRAMFILES64\Echelon"
!define UNINSTALL_KEY   "Software\Microsoft\Windows\CurrentVersion\Uninstall\Echelon"
!define REG_INSTALL_KEY "Software\Echelon"
!define VCREDIST_KEY    "SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "Echelon-Setup.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKLM "${REG_INSTALL_KEY}" "Install_Dir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
BrandingText "Echelon by Zero"
ShowInstDetails show

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON                "assets\icons\echelon.ico"
!define MUI_UNICON              "assets\icons\echelon.ico"
!define MUI_WELCOMEPAGE_TITLE   "Welcome to Echelon v${APP_VERSION}"
!define MUI_WELCOMEPAGE_TEXT    "Echelon lets you swap your face in real-time during any video call.$\r$\n$\r$\nWorks with Zoom, Google Meet, Discord, WhatsApp, and Teams.$\r$\n$\r$\nCreated by Zero."
!define MUI_FINISHPAGE_RUN      "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch Echelon now"
!define MUI_FINISHPAGE_LINK     "github.com/gengenesix/echelon"
!define MUI_FINISHPAGE_LINK_LOCATION "https://github.com/gengenesix/echelon"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ── Check VC++ installed ──────────────────────────────────────────
Function CheckVCRedistInstalled
  ReadRegDWORD $0 HKLM "${VCREDIST_KEY}" "Installed"
  ${If} $0 == 1
    Push 1
    Return
  ${EndIf}
  ReadRegStr $0 HKLM "${VCREDIST_KEY}" "Version"
  ${If} $0 != ""
    Push 1
    Return
  ${EndIf}
  Push 0
FunctionEnd

; ═══════════════════════════════════════════════════════════════════
; MAIN INSTALL SECTION
; ═══════════════════════════════════════════════════════════════════
Section "Echelon" SecMain
  SectionIn RO

  ; ── Step 1: Kill running process silently ──
  nsExec::Exec 'cmd /c taskkill /F /IM "${APP_EXE}" /T 2>nul 1>nul'
  Pop $0
  Sleep 2000

  ; ── Step 2: Run previous uninstaller silently if found ──
  ReadRegStr $R0 HKLM "${UNINSTALL_KEY}" "QuietUninstallString"
  ${If} $R0 != ""
    ExecWait '$R0'
    Sleep 1500
  ${EndIf}

  ; ── Step 3: Clear old install dir ──
  ${If} ${FileExists} "$INSTDIR\*.*"
    RMDir /r "$INSTDIR"
    Sleep 500
  ${EndIf}

  ; ── Step 4: Install VC++ if needed ──
  DetailPrint "Checking Visual C++ Runtime..."
  Call CheckVCRedistInstalled
  Pop $0
  ${If} $0 != 1
    DetailPrint "Installing Visual C++ 2015-2022 Runtime..."
    SetOutPath "$TEMP\EchelonSetup"
    ClearErrors
    File "vc_redist.x64.exe"
    ${IfNot} ${Errors}
      ExecWait '"$TEMP\EchelonSetup\vc_redist.x64.exe" /quiet /norestart'
      Delete "$TEMP\EchelonSetup\vc_redist.x64.exe"
      RMDir "$TEMP\EchelonSetup"
    ${EndIf}
  ${Else}
    DetailPrint "Visual C++ Runtime already installed."
  ${EndIf}

  ; ── Step 5: Extract app files ──
  DetailPrint "Installing Echelon ${APP_VERSION}..."
  SetOverwrite on
  ClearErrors
  SetOutPath "$INSTDIR"
  File /r "dist\Echelon\*.*"

  ${If} ${Errors}
    RMDir /r "$INSTDIR"
    MessageBox MB_OK|MB_ICONSTOP "Installation failed: could not write files.$\r$\nPlease run as Administrator and disable antivirus temporarily."
    Abort
  ${EndIf}

  ; ── Step 6: Registry ──
  WriteRegStr   HKLM "${REG_INSTALL_KEY}"  "Install_Dir"          "$INSTDIR"
  WriteRegStr   HKLM "${UNINSTALL_KEY}"    "DisplayName"          "Echelon"
  WriteRegStr   HKLM "${UNINSTALL_KEY}"    "UninstallString"      '"$INSTDIR\uninstall.exe"'
  WriteRegStr   HKLM "${UNINSTALL_KEY}"    "QuietUninstallString" '"$INSTDIR\uninstall.exe" /S'
  WriteRegStr   HKLM "${UNINSTALL_KEY}"    "InstallLocation"      "$INSTDIR"
  WriteRegStr   HKLM "${UNINSTALL_KEY}"    "DisplayIcon"          "$INSTDIR\${APP_EXE},0"
  WriteRegStr   HKLM "${UNINSTALL_KEY}"    "Publisher"            "${APP_PUBLISHER}"
  WriteRegStr   HKLM "${UNINSTALL_KEY}"    "DisplayVersion"       "${APP_VERSION}"
  WriteRegStr   HKLM "${UNINSTALL_KEY}"    "URLInfoAbout"         "https://github.com/gengenesix/echelon"
  WriteRegDWORD HKLM "${UNINSTALL_KEY}"    "NoModify"             1
  WriteRegDWORD HKLM "${UNINSTALL_KEY}"    "NoRepair"             1

  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "EstimatedSize" "$0"

  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Start Menu Shortcuts"
  CreateDirectory "$SMPROGRAMS\Echelon"
  CreateShortcut  "$SMPROGRAMS\Echelon\Echelon.lnk"   "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  CreateShortcut  "$SMPROGRAMS\Echelon\Uninstall.lnk" "$INSTDIR\uninstall.exe"
SectionEnd

Section "Desktop Shortcut"
  CreateShortcut "$DESKTOP\Echelon.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
SectionEnd

Section "Uninstall"
  nsExec::Exec 'cmd /c taskkill /F /IM "${APP_EXE}" /T 2>nul 1>nul'
  Pop $0
  Sleep 1500
  RMDir /r "$INSTDIR"
  Delete "$SMPROGRAMS\Echelon\Echelon.lnk"
  Delete "$SMPROGRAMS\Echelon\Uninstall.lnk"
  RMDir  "$SMPROGRAMS\Echelon"
  Delete "$DESKTOP\Echelon.lnk"
  DeleteRegKey HKLM "${UNINSTALL_KEY}"
  DeleteRegKey HKLM "${REG_INSTALL_KEY}"
  MessageBox MB_YESNO "Remove Echelon settings and saved faces?" IDNO done
    RMDir /r "$APPDATA\Echelon"
  done:
SectionEnd
