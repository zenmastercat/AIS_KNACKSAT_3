{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  packages = [
    pkgs.git
    pkgs.htop
    pkgs.uv
    # Define Python along with its required libraries inside Nix
    (pkgs.python3.withPackages (ps: with ps; [
      numpy
      matplotlib
    ]))
  ];

  # Fix for dynamically linked C libraries if using uv/pip-installed wheels inside nix-shell
  shellHook = ''
    export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH"
  '';
}