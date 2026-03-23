; Echelon Windows Installer Script
; Created by Zero

!define APP_NAME "Echelon"
!define APP_VERSION "2.0.0"
!define APP_PUBLISHER "Zero"
!define APP_URL "https://github.com/zeroxdev/echelon"
!define APP_EXE "Echelon.exe"
!define INSTALL_DIR "$PROGRAMFILES64\Echelon"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "Echelon-Setup.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKLM "Software\Echelon" "Install_Dir"
RequestExecutionLevel admin
BrandingText "Echelon by Zero"

; Modern UI
!include "MUI2.nsh"
!define MUI_ABORTWARNING
!define MUI_ICON "assets\icons\echelon.ico"
!define MUI_UNICON "assets\icons\echelon.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "assets\icons\icon_256.png"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "assets\icons\icon_128.png"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch Echelon now"
!insertmacro MUI_PAGE_FINISH

; Uninstall pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; Installation
Section "Echelon" SecMain
  SetOutPath "$INSTDIR"
  File /r "dist\Echelon\*.*"

  ; Write registry for uninstaller
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Echelon" "DisplayName" "Echelon"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Echelon" "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Echelon" "DisplayIcon" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Echelon" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Echelon" "DisplayVersion" "${APP_VERSION}"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Echelon" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Echelon" "NoRepair" 1

  ; Start menu shortcut
  CreateDirectory "$SMPROGRAMS\Echelon"
  CreateShortcut "$SMPROGRAMS\Echelon\Echelon.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  CreateShortcut "$SMPROGRAMS\Echelon\Uninstall.lnk" "$INSTDIR\uninstall.exe"

  ; Desktop shortcut
  CreateShortcut "$DESKTOP\Echelon.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0

  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

; Uninstaller
Section "Uninstall"
  RMDir /r "$INSTDIR"
  Delete "$SMPROGRAMS\Echelon\Echelon.lnk"
  Delete "$SMPROGRAMS\Echelon\Uninstall.lnk"
  RMDir "$SMPROGRAMS\Echelon"
  Delete "$DESKTOP\Echelon.lnk"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Echelon"
  DeleteRegKey HKLM "Software\Echelon"
SectionEnd
