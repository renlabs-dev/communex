{
  description = "Alternative library/SDK to the original Commune AI";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs?ref=23.11";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { system=system; };
      in
      {
        packages.default = pkgs.mkShell {
	  buildInputs = [
	    pkgs.python311
	    pkgs.python311Packages.ipython
	    pkgs.ruff
	    pkgs.poetry
	  ];
	};
      });
}
