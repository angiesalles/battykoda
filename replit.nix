{ pkgs }: {
  deps = [
    pkgs.python310
    pkgs.python310Packages.flask
    pkgs.python310Packages.flask-login
    pkgs.python310Packages.flask-sqlalchemy
    pkgs.python310Packages.werkzeug
    pkgs.python310Packages.scipy
    pkgs.python310Packages.numpy
    pkgs.python310Packages.matplotlib
    pkgs.python310Packages.pillow
    pkgs.python310Packages.sqlalchemy
    pkgs.python310Packages.wtforms
    pkgs.python310Packages.email-validator
    pkgs.python310Packages.pip
    pkgs.r-base
    pkgs.rPackages.tuneR
    pkgs.rPackages.randomForest
  ];
}