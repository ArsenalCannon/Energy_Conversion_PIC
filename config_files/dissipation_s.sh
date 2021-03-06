#!/bin/bash

ana_path=/net/scratch3/xiaocanli/pic_analysis
ana_config=$ana_path/config_files/analysis_config.dat
conf=$ana_path/config_files/conf.dat
ch_inductive () {
    sed -i -e "s/\(inductive = \).*/\1$1/" $ana_config
}
ch_tp2 () {
    sed -i -e "s/\(tp2 = \).*/\1$1/" $ana_config
}

ch_htt () {
    sed -i -e "s/\(httx = \).*,\(.*\)/\1$1,\2/" $conf
    sed -i -e "s/\(htty = \).*,\(.*\)/\1$2,\2/" $conf
    sed -i -e "s/\(httz = \).*,\(.*\)/\1$3,\2/" $conf
}

mpi_sizes=16

run_dissipation () {
    cd $ana_path
    mpirun -np $mpi_sizes ./dissipation.exec -rp $1 -sp $2
    ch_inductive 1
    mpirun -np $mpi_sizes ./dissipation.exec -rp $1 -sp $2
    ch_inductive 0
    mkdir -p data/jdote_data/$3
    mv data/*.gda data/jdote_data/$3
}

run_compression () {
    cd $ana_path
    mpirun -np $mpi_sizes ./compression.exec -rp $1 $3
    mkdir -p data/compression/$2
    mv data/*.gda data/compression/$2
}

# runs_path=/net/scratch3/xiaocanli/reconnection
runs_path=/net/scratch3/xiaocanli/reconnection/frequent_dump

# run_name=mime25-sigma1-beta002-guide02
# rootpath=$runs_path/$run_name-200-100/
# ch_tp2 235
# run_dissipation $rootpath e $run_name
# run_dissipation $rootpath i $run_name

# run_name=mime25-sigma1-beta002-guide05
# rootpath=$runs_path/$run_name-200-100/
# ch_tp2 241
# run_dissipation $rootpath e $run_name
# run_dissipation $rootpath i $run_name

# run_name=mime25-sigma1-beta002-guide10
# rootpath=$runs_path/$run_name-200-100/
# ch_tp2 241
# run_dissipation $rootpath e $run_name
# run_dissipation $rootpath i $run_name

# run_name=mime25-sigma1-beta002-guide00
# rootpath=$runs_path/$run_name-200-100/
# ch_tp2 204
# run_dissipation $rootpath e $run_name
# run_dissipation $rootpath i $run_name

# run_name=mime25-sigma1-beta008-guide00
# rootpath=$runs_path/$run_name-200-100/
# ch_tp2 241
# run_dissipation $rootpath e $run_name
# run_dissipation $rootpath i $run_name

# run_name=mime25-sigma1-beta032-guide00
# rootpath=$runs_path/$run_name-200-100/
# ch_tp2 241
# run_dissipation $rootpath e $run_name
# run_dissipation $rootpath i $run_name

# run_name=dump_test
# rootpath=$runs_path/$run_name/
# ch_tp2 35
# run_dissipation $rootpath e $run_name
# run_dissipation $rootpath i $run_name

# run_name=high_beta_test
# rootpath=$runs_path/$run_name/
# ch_tp2 41
# run_dissipation $rootpath e $run_name
# run_dissipation $rootpath i $run_name

# run_name=mime25_beta002_guide00_frequent_dump
# rootpath=$runs_path/$run_name/
# ch_tp2 161
# run_dissipation $rootpath e $run_name
# run_dissipation $rootpath i $run_name

# run_name=mime25_beta002_guide02_frequent_dump
# rootpath=$runs_path/$run_name/
# ch_tp2 161
# run_dissipation $rootpath e $run_name
# run_dissipation $rootpath i $run_name

# run_name=mime25_beta002_guide05_frequent_dump
# rootpath=$runs_path/$run_name/
# ch_tp2 161
# run_dissipation $rootpath e $run_name
# run_dissipation $rootpath i $run_name

# run_name=mime25_beta002_guide10_frequent_dump
# rootpath=$runs_path/$run_name/
# ch_tp2 161
# run_dissipation $rootpath e $run_name
# run_dissipation $rootpath i $run_name

run_name=mime25_beta008_guide00_frequent_dump
rootpath=$runs_path/$run_name/
ch_tp2 161
run_dissipation $rootpath e $run_name
run_dissipation $rootpath i $run_name

run_name=mime25_beta032_guide00_frequent_dump
rootpath=$runs_path/$run_name/
ch_tp2 161
run_dissipation $rootpath e $run_name
run_dissipation $rootpath i $run_name

# run_name=mime25-sigma1-beta002-guide02
# rootpath=$runs_path/$run_name-200-100/
# ch_tp2 235
# run_compression $rootpath $run_name

# run_name=mime25-sigma1-beta002-guide05
# rootpath=$runs_path/$run_name-200-100/
# ch_tp2 241
# run_compression $rootpath $run_name

# run_name=mime25-sigma1-beta002-guide10
# rootpath=$runs_path/$run_name-200-100/
# ch_tp2 241
# run_compression $rootpath $run_name

# run_name=mime25-sigma1-beta002-guide00
# rootpath=$runs_path/$run_name-200-100/
# ch_tp2 204
# run_compression $rootpath $run_name

# run_name=mime25-sigma1-beta008-guide00
# rootpath=$runs_path/$run_name-200-100/
# ch_tp2 241
# run_compression $rootpath $run_name

# run_name=mime25-sigma1-beta032-guide00
# rootpath=$runs_path/$run_name-200-100/
# ch_tp2 241
# run_compression $rootpath $run_name

# run_name=dump_test
# rootpath=$runs_path/$run_name/
# ch_tp2 35
# run_compression $rootpath $run_name -uexb
# run_compression $rootpath $run_name

# run_name=high_beta_test
# rootpath=$runs_path/$run_name/
# ch_tp2 41
# run_compression $rootpath $run_name -uexb
# run_compression $rootpath $run_name

# run_name=mime25_beta002_guide00_frequent_dump
# rootpath=$runs_path/$run_name/
# ch_tp2 161
# run_compression $rootpath $run_name -uexb
# run_compression $rootpath $run_name

# run_name=mime25_beta002_guide02_frequent_dump
# rootpath=$runs_path/$run_name/
# ch_tp2 161
# run_compression $rootpath $run_name -uexb
# run_compression $rootpath $run_name

# run_name=mime25_beta002_guide05_frequent_dump
# rootpath=$runs_path/$run_name/
# ch_tp2 161
# run_compression $rootpath $run_name -uexb
# run_compression $rootpath $run_name

# run_name=mime25_beta002_guide10_frequent_dump
# rootpath=$runs_path/$run_name/
# ch_tp2 161
# run_compression $rootpath $run_name -uexb
# run_compression $rootpath $run_name

run_name=mime25_beta008_guide00_frequent_dump
rootpath=$runs_path/$run_name/
ch_tp2 161
run_compression $rootpath $run_name -uexb
run_compression $rootpath $run_name

run_name=mime25_beta032_guide00_frequent_dump
rootpath=$runs_path/$run_name/
ch_tp2 161
run_compression $rootpath $run_name -uexb
run_compression $rootpath $run_name
