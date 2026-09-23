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
              pkgs.ruff
            ];
          };
        });
      packages = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
        in {
          # @planks("Given the PCE Nix package is installed")
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

              mkdir -p $out/bin $out/libexec
              cp packaging/run_loop.py $out/libexec/run_loop.py
              cat > $out/bin/pce <<EOF
              #!${pkgs.runtimeShell}
              exec ${pkgs.python3}/bin/python3 $out/libexec/run_loop.py "\$@"
              EOF
              chmod +x $out/bin/pce

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
