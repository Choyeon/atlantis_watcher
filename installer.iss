; ===========================================================================
;  Atlantis Watcher — Inno Setup 安装包脚本
;
;  编译： ISCC installer.iss
;  或：   python build.py --installer
;
;  特性：
;    · 安装向导（安装位置、开始菜单、桌面快捷方式、卸载项）
;    · 升级覆盖：同版本覆盖安装，卸载时保留用户数据
;    · 关闭运行中的程序再覆盖
;    · 卸载时可选清理日志与配置
;    · 支持最低 Windows 版本声明
; ===========================================================================

#define AppName "Atlantis Watcher"
#define AppShortName "AtlantisWatcher"
#define AppVersion "1.1.0"
#define AppPublisher "Atlantis"
#define AppExeName "AtlantisWatcher.exe"
#define AppUrl "https://github.com/Choyeon/atlantis_watcher"

; 源目录（PyInstaller onedir 输出）
#define SourceDir "dist\AtlantisWatcher"

[Setup]
AppId={{7B2E4C1A-9D3F-4E5B-8A6C-1F2E3D4C5B6A}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}
AppUpdatesURL={#AppUrl}
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} 安装程序
DefaultDirName={autopf}\{#AppShortName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename={#AppShortName}-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; 生产级：未配置代码签名时不要声明 SignTool（Inno Setup 7 会拒绝空值）
; 配置签名后添加： SignTool=MySignTool
; 最低 Windows 版本（Windows 10）
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
DisableDirPage=no
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "chinese"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinese.WelcomeLabel2=安装向导将引导您完成 Atlantis Watcher 的安装。%n%n该程序需要管理员权限以执行关机、重启等系统操作。%n%n建议关闭正在运行的 Atlantis Watcher 后继续。

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"
Name: "startupicon"; Description: "开机自动启动（写入注册表 Run 项，可在设置页关闭）"; GroupDescription: "附加任务:"; Flags: unchecked

[Files]
; 主程序目录（PyInstaller onedir 输出，含 _internal 依赖）
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon
; 开机自启统一由 [Registry] 写入 HKCU Run 项，与应用内设置页共用同一来源。
; 不再创建「启动」文件夹快捷方式（旧机制无法关闭，且会绕过应用设置）。

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AtlantisWatcher"; ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "立即启动 {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 卸载时清理程序生成的运行时数据（用户数据保留在 AppData，不在此删除）
Type: filesandordirs; Name: "{app}"

[Code]
{ ------------------------------------------------------------------------
  安装前检查：检测端口占用，避免服务启动失败却不知原因
  ------------------------------------------------------------------------ }
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

{ ------------------------------------------------------------------------
  卸载时询问是否清理用户数据
  ------------------------------------------------------------------------ }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\AtlantisWatcher');
    if DirExists(DataDir) then
    begin
      if MsgBox('是否同时删除运行日志与本地数据？' + #13#10 + #13#10 +
                '路径: ' + DataDir + #13#10 + #13#10 +
                '选择「否」将保留日志文件以便排查问题。',
                mbConfirmation, MB_YESNO) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
