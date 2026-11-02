#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName "Factoria"
#define MyAppPublisher "Sergi Escoruela"
#define MyAppExeName "Factoria.exe"
#define MyAppId "{C23F0F33-5A4F-4C34-BE7A-6CB663AA5A88}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Factoria
DefaultGroupName=Factoria
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist\installer
OutputBaseFilename=Factoria-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesEnvironment=yes

[Tasks]
Name: "addtopath"; Description: "Add Factoria to my user PATH"; GroupDescription: "Command line integration:"; Flags: checkedonce

[Files]
Source: "..\..\dist\Factoria.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Factoria"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{userdocs}"
Name: "{group}\Uninstall Factoria"; Filename: "{uninstallexe}"

[Registry]
Root: HKCU; Subkey: "Software\Factoria"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Factoria"; ValueType: dword; ValueName: "PathAdded"; ValueData: "1"; Tasks: addtopath

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--version"; Description: "Verify Factoria installation"; Flags: postinstall nowait skipifsilent unchecked

[Code]
const
  EnvironmentKey = 'Environment';
  FactoriaKey = 'Software\Factoria';

function NormalizePathEntry(Value: string): string;
begin
  Result := RemoveQuotes(Trim(Value));
  while (Length(Result) > 3) and (Result[Length(Result)] = '\') do
    Delete(Result, Length(Result), 1);
  Result := Lowercase(Result);
end;

function PathContains(CurrentPath, Entry: string): Boolean;
var
  Parts: TArrayOfString;
  I: Integer;
begin
  Result := False;
  Parts := StringSplit(CurrentPath, [';'], stExcludeEmpty);
  for I := 0 to GetArrayLength(Parts) - 1 do
    if NormalizePathEntry(Parts[I]) = NormalizePathEntry(Entry) then
    begin
      Result := True;
      Exit;
    end;
end;

procedure AddToUserPath;
var
  CurrentPath: string;
  NewPath: string;
begin
  if not RegQueryStringValue(HKCU, EnvironmentKey, 'Path', CurrentPath) then
    CurrentPath := '';

  if PathContains(CurrentPath, ExpandConstant('{app}')) then
    Exit;

  if CurrentPath = '' then
    NewPath := ExpandConstant('{app}')
  else if CurrentPath[Length(CurrentPath)] = ';' then
    NewPath := CurrentPath + ExpandConstant('{app}')
  else
    NewPath := CurrentPath + ';' + ExpandConstant('{app}');

  RegWriteExpandStringValue(HKCU, EnvironmentKey, 'Path', NewPath);
end;

procedure RemoveFromUserPath;
var
  CurrentPath: string;
  Parts: TArrayOfString;
  I: Integer;
  NewPath: string;
  Entry: string;
begin
  if not RegQueryStringValue(HKCU, EnvironmentKey, 'Path', CurrentPath) then
    Exit;

  Entry := ExpandConstant('{app}');
  Parts := StringSplit(CurrentPath, [';'], stExcludeEmpty);
  NewPath := '';
  for I := 0 to GetArrayLength(Parts) - 1 do
  begin
    if NormalizePathEntry(Parts[I]) <> NormalizePathEntry(Entry) then
    begin
      if NewPath <> '' then
        NewPath := NewPath + ';';
      NewPath := NewPath + Parts[I];
    end;
  end;

  RegWriteExpandStringValue(HKCU, EnvironmentKey, 'Path', NewPath);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('addtopath') then
    AddToUserPath;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  PathAdded: Cardinal;
begin
  if CurUninstallStep = usUninstall then
  begin
    if RegQueryDWordValue(HKCU, FactoriaKey, 'PathAdded', PathAdded) and (PathAdded = 1) then
      RemoveFromUserPath;
  end;
end;
