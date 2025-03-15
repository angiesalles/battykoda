{ pkgs }: {
  deps = [
    # Python
    pkgs.python312
    
    # R and core packages
    pkgs.r-base
    pkgs.rPackages.devtools
    pkgs.rPackages.remotes
    pkgs.rPackages.BiocManager
    
    # Audio processing packages
    pkgs.rPackages.tuneR
    pkgs.rPackages.seewave
    pkgs.rPackages.audio
    
    # Data handling packages
    pkgs.rPackages.stringr
    pkgs.rPackages.jsonlite
    
    # Machine learning packages
    pkgs.rPackages.kknn
    pkgs.rPackages.mlr3
    pkgs.rPackages.mlr3learners
    pkgs.rPackages.mlr3tuning
    
    # System dependencies for R package compilation
    pkgs.libffi
    pkgs.libxml2
    pkgs.libsndfile
    pkgs.fftw
    pkgs.zlib
    pkgs.bzip2
    pkgs.stdenv.cc.cc.lib
    
    # Development tools
    pkgs.gcc
    pkgs.gnumake
    pkgs.glibc
  ];
  
  env = {
    LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
      pkgs.libsndfile
      pkgs.fftw
      pkgs.zlib
      pkgs.bzip2
      pkgs.stdenv.cc.cc.lib
    ];
  };
}