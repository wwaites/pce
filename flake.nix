{
  description = "Artificial Organisation skill pack";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in {
      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in {
          default = pkgs.mkShell {
            packages = [
              (pkgs.python3.withPackages (ps: [ ps.behave ps.coverage ]))
            ];
          };
        });
      packages = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in {
          default = pkgs.stdenvNoCC.mkDerivation {
            pname = "artificial-org-skills";
            version = "0.1.0";
            src = ./.;
            nativeBuildInputs = [ pkgs.python3 ];
            doCheck = true;

            checkPhase = ''
              python3 packaging/sync-adapters.py --check
            '';

            installPhase = ''
              mkdir -p $out/share/artificial-org
              cp -R skills-core schemas templates $out/share/artificial-org/

              mkdir -p $out/share/opencode-skills
              cp -R adapters/opencode/skills/* $out/share/opencode-skills/

              mkdir -p $out/share/claude-skills
              cp -R adapters/claude/skills/* $out/share/claude-skills/
            '';
          };
        });
      checks = forAllSystems (system: {
        adapter-sync = self.packages.${system}.default;
      });
    };
}
