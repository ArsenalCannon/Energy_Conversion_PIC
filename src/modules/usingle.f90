!*******************************************************************************
! Module of bulk flow velocity for single fluid.
!*******************************************************************************
module usingle
    use constants, only: fp
    implicit none
    private
    public vsx, vsy, vsz    ! s indicates 'single fluid'
    public init_usingle, free_usingle, calc_usingle, &
           open_velocity_density_files, close_velocity_density_files, &
           read_velocity_density, init_one_fluild_velocity, &
           free_one_fluild_velocity, open_one_fluid_velocity, &
           read_one_fluid_velocity, close_one_fluid_velocity
    real(fp), allocatable, dimension(:, :, :) :: vsx, vsy, vsz
    real(fp), allocatable, dimension(:, :, :) :: vx, vy, vz
    real(fp), allocatable, dimension(:, :, :) :: nrho_a, nrho_b
    integer, dimension(3) :: fh_vel     ! File handler for velocity field.
    integer, dimension(3) :: fh_vel_b   ! For the other species.
    integer :: fh_nrho    ! File handler for number density.
    integer :: fh_nrho_b  ! For the other species.

    interface init_usingle
        module procedure &
            init_usingle_s, init_usingle_b
    end interface init_usingle

    interface free_usingle
        module procedure &
            free_usingle_s, free_usingle_b
    end interface free_usingle

    interface open_velocity_density_files
        module procedure &
            open_velocity_density_files_s, open_velocity_density_files_b
    end interface open_velocity_density_files

    interface read_velocity_density
        module procedure &
            read_velocity_density_s, read_velocity_density_b
    end interface read_velocity_density

    interface close_velocity_density_files
        module procedure &
            close_velocity_density_files_s, close_velocity_density_files_b
    end interface close_velocity_density_files

    interface calc_usingle
        module procedure &
            calc_usingle_s, calc_usingle_b
    end interface calc_usingle

    contains

    !---------------------------------------------------------------------------
    ! Initialize the bulk flow velocity for single fluid.
    !---------------------------------------------------------------------------
    subroutine init_usingle_s
        use mpi_topology, only: htg
        implicit none
        call init_one_fluild_velocity
        allocate(nrho_a(htg%nx, htg%ny, htg%nz))
    end subroutine init_usingle_s

    subroutine init_usingle_b(species)
        use mpi_topology, only: htg
        implicit none
        character(*), intent(in) :: species
        call init_one_fluild_velocity
        allocate(vx(htg%nx, htg%ny, htg%nz))
        allocate(vy(htg%nx, htg%ny, htg%nz))
        allocate(vz(htg%nx, htg%ny, htg%nz))
        allocate(nrho_a(htg%nx, htg%ny, htg%nz))
        allocate(nrho_b(htg%nx, htg%ny, htg%nz))
    end subroutine init_usingle_b

    subroutine init_one_fluild_velocity
        use mpi_topology, only: htg
        implicit none
        allocate(vsx(htg%nx, htg%ny, htg%nz))
        allocate(vsy(htg%nx, htg%ny, htg%nz))
        allocate(vsz(htg%nx, htg%ny, htg%nz))
    end subroutine init_one_fluild_velocity

    !---------------------------------------------------------------------------
    ! Free the bulk flow velocity for single fluid.
    !---------------------------------------------------------------------------
    subroutine free_usingle_s
        implicit none
        deallocate(vsx, vsy, vsz)
        deallocate(nrho_a)
    end subroutine free_usingle_s

    subroutine free_usingle_b(species)
        implicit none
        character(*), intent(in) :: species
        deallocate(vsx, vsy, vsz)
        deallocate(vx, vy, vz)
        deallocate(nrho_a, nrho_b)
    end subroutine free_usingle_b

    subroutine free_one_fluild_velocity
        implicit none
        deallocate(vsx, vsy, vsz)
    end subroutine free_one_fluild_velocity

    !---------------------------------------------------------------------------
    ! Open one-fluid velocity files
    ! Inputs:
    !   ct: current time step (optional)
    !---------------------------------------------------------------------------
    subroutine open_one_fluid_velocity(ct)
        implicit none
        integer, intent(in), optional :: ct
        character(len=1) :: species_other
        fh_vel = 0
        if (present(ct)) then
            call open_one_fluid_velocity_t(fh_vel, ct)
        else
            call open_one_fluid_velocity_t(fh_vel)
        endif
    end subroutine open_one_fluid_velocity

    !---------------------------------------------------------------------------
    ! Open the data files of one-fluid velocity fields
    ! Outputs:
    !   fh_vel_t: file handlers
    !---------------------------------------------------------------------------
    subroutine open_one_fluid_velocity_t(fh_vel_t, ct)
        use mpi_module
        use path_info, only: filepath
        use mpi_info_module, only: fileinfo
        use mpi_io_module, only: open_data_mpi_io
        implicit none
        integer, dimension(3), intent(out) :: fh_vel_t
        integer, intent(in), optional :: ct
        integer :: file_size
        character(len=256) :: fname
        logical :: ex, is_opened
        character(len=1) :: vel
        character(len=16) :: cfname
        integer :: fh
        if (present(ct)) then
            write(cfname, "(I0)") ct
            fname = trim(adjustl(filepath))//'vx_'//trim(cfname)//'.gda'
        else
            fname = trim(adjustl(filepath))//'vx.gda'
        endif
        inquire(file=fname, exist=ex, size=file_size)
        if (ex .and. file_size .ne. 0) then
            vel = 'v'
        else
            vel = 'u'
        endif

        fh_vel_t = 0

        if (present(ct)) then
            fname = trim(adjustl(filepath))//vel//'x_'//trim(cfname)//'.gda'
        else
            fname = trim(adjustl(filepath))//vel//'x.gda'
        endif
        inquire(file=fname, opened=is_opened, number=fh)
        if (is_opened) then
            fh_vel_t(1) = fh
        else
            call open_data_mpi_io(fname, MPI_MODE_RDONLY, fileinfo, &
                fh_vel_t(1))
        endif

        if (present(ct)) then
            fname = trim(adjustl(filepath))//vel//'y_'//trim(cfname)//'.gda'
        else
            fname = trim(adjustl(filepath))//vel//'y.gda'
        endif
        inquire(file=fname, opened=is_opened, number=fh)
        if (is_opened) then
            fh_vel_t(2) = fh
        else
            call open_data_mpi_io(fname, MPI_MODE_RDONLY, fileinfo, &
                fh_vel_t(2))
        endif

        if (present(ct)) then
            fname = trim(adjustl(filepath))//vel//'z_'//trim(cfname)//'.gda'
        else
            fname = trim(adjustl(filepath))//vel//'z.gda'
        endif
        inquire(file=fname, opened=is_opened, number=fh)
        if (is_opened) then
            fh_vel_t(3) = fh
        else
            call open_data_mpi_io(fname, MPI_MODE_RDONLY, fileinfo, &
                fh_vel_t(3))
        endif

    end subroutine open_one_fluid_velocity_t

    !---------------------------------------------------------------------------
    ! Open the data files of velocity fields and number density for the other
    ! species. e.g. when the current species is electron, this procedure will
    ! open velocity files for ions.
    ! Inputs:
    !   species: particle species. 'e' for electron. 'i' for ion.
    !   ct: current time step (optional)
    !---------------------------------------------------------------------------
    subroutine open_velocity_density_files_s(species, ct)
        implicit none
        character(*), intent(in) :: species
        integer, intent(in), optional :: ct
        character(len=1) :: species_other
        if (species == 'e') then
            species_other = 'i'
        else
            species_other = 'e'
        endif
        fh_vel = 0
        if (present(ct)) then
            call open_velocity_density_fieles_t(species_other, fh_vel, fh_nrho, ct)
        else
            call open_velocity_density_fieles_t(species_other, fh_vel, fh_nrho)
        endif
    end subroutine open_velocity_density_files_s

    !---------------------------------------------------------------------------
    ! Open the data files of velocity fields and number density for one particle
    ! species.
    ! Inputs:
    !   species: particle species. 'e' for electron. 'i' for ion.
    !   ! 3-velocity is saved as ux, uy, uz in non-relativistic cases
    ! Outputs:
    !   fh_vel_t, fh_nrho_t: file handlers
    !---------------------------------------------------------------------------
    subroutine open_velocity_density_fieles_t(species, fh_vel_t, fh_nrho_t, ct)
        use mpi_module
        use path_info, only: filepath
        use mpi_info_module, only: fileinfo
        use mpi_io_module, only: open_data_mpi_io
        implicit none
        character(*), intent(in) :: species
        integer, dimension(3), intent(out) :: fh_vel_t
        integer, intent(out) :: fh_nrho_t
        integer, intent(in), optional :: ct
        integer :: file_size
        character(len=256) :: fname
        logical :: ex, is_opened
        character(len=1) :: vel
        character(len=16) :: cfname
        integer :: fh
        if (present(ct)) then
            write(cfname, "(I0)") ct
            fname = trim(adjustl(filepath))//'v'//species//'x_'//trim(cfname)//'.gda'
        else
            fname = trim(adjustl(filepath))//'v'//species//'x.gda'
        endif
        inquire(file=fname, exist=ex, size=file_size)
        if (ex .and. file_size .ne. 0) then
            vel = 'v'
        else
            vel = 'u'
        endif

        fh_vel_t = 0
        fh_nrho_t = 0

        if (present(ct)) then
            fname = trim(adjustl(filepath))//vel//species//'x_'//trim(cfname)//'.gda'
        else
            fname = trim(adjustl(filepath))//vel//species//'x.gda'
        endif
        inquire(file=fname, opened=is_opened, number=fh)
        if (is_opened) then
            fh_vel_t(1) = fh
        else
            call open_data_mpi_io(fname, MPI_MODE_RDONLY, fileinfo, &
                fh_vel_t(1))
        endif

        if (present(ct)) then
            fname = trim(adjustl(filepath))//vel//species//'y_'//trim(cfname)//'.gda'
        else
            fname = trim(adjustl(filepath))//vel//species//'y.gda'
        endif
        inquire(file=fname, opened=is_opened, number=fh)
        if (is_opened) then
            fh_vel_t(2) = fh
        else
            call open_data_mpi_io(fname, MPI_MODE_RDONLY, fileinfo, &
                fh_vel_t(2))
        endif

        if (present(ct)) then
            fname = trim(adjustl(filepath))//vel//species//'z_'//trim(cfname)//'.gda'
        else
            fname = trim(adjustl(filepath))//vel//species//'z.gda'
        endif
        inquire(file=fname, opened=is_opened, number=fh)
        if (is_opened) then
            fh_vel_t(3) = fh
        else
            call open_data_mpi_io(fname, MPI_MODE_RDONLY, fileinfo, &
                fh_vel_t(3))
        endif

        if (present(ct)) then
            fname = trim(adjustl(filepath))//'n'//species//'_'//trim(cfname)//'.gda'
        else
            fname = trim(adjustl(filepath))//'n'//species//'.gda'
        endif
        inquire(file=fname, opened=is_opened, number=fh)
        if (is_opened) then
            fh_nrho_t = fh
        else
            call open_data_mpi_io(fname, MPI_MODE_RDONLY, fileinfo, fh_nrho_t)
        endif
    end subroutine open_velocity_density_fieles_t

    !---------------------------------------------------------------------------
    ! Open the data files of velocity fields and number density for both
    ! species.
    !---------------------------------------------------------------------------
    subroutine open_velocity_density_files_b(ct)
        use path_info, only: filepath
        use mpi_info_module, only: fileinfo
        implicit none
        integer, intent(in), optional :: ct
        character(len=100) :: fname
        fh_vel = 0
        fh_nrho = 0
        fh_vel_b = 0
        fh_nrho_b = 0
        if (present(ct)) then
            call open_velocity_density_fieles_t('e', fh_vel, fh_nrho, ct)
            call open_velocity_density_fieles_t('i', fh_vel_b, fh_nrho_b, ct)
        else
            call open_velocity_density_fieles_t('e', fh_vel, fh_nrho)
            call open_velocity_density_fieles_t('i', fh_vel_b, fh_nrho_b)
        endif
    end subroutine open_velocity_density_files_b

    !---------------------------------------------------------------------------
    ! Close one-fluid velocity files.
    !---------------------------------------------------------------------------
    subroutine close_one_fluid_velocity
        use mpi_module
        implicit none
        integer :: i
        logical :: is_opened
        inquire(fh_vel(1), opened=is_opened)
        if (is_opened) then
            do i = 1, 3
                call MPI_FILE_CLOSE(fh_vel(i), ierror)
            enddo
        endif
    end subroutine close_one_fluid_velocity

    !---------------------------------------------------------------------------
    ! Close the data file of velocity field and number density for one species.
    ! Input:
    !   species: particle species. 'e' for electron. 'i' for ion.
    !---------------------------------------------------------------------------
    subroutine close_velocity_density_files_s(species)
        use mpi_module
        implicit none
        character(*), intent(in) :: species
        integer :: i
        logical :: is_opened
        inquire(fh_vel(1), opened=is_opened)
        if (is_opened) then
            do i = 1, 3
                call MPI_FILE_CLOSE(fh_vel(i), ierror)
            enddo
        endif
        inquire(fh_nrho, opened=is_opened)
        if (is_opened) then
            call MPI_FILE_CLOSE(fh_nrho)
        endif
    end subroutine close_velocity_density_files_s

    !---------------------------------------------------------------------------
    ! Close the data file of velocity field and number density for both species.
    !---------------------------------------------------------------------------
    subroutine close_velocity_density_files_b
        use mpi_module
        implicit none
        integer :: i
        logical :: is_opened
        inquire(fh_vel(1), opened=is_opened)
        if (is_opened) then
            do i = 1, 3
                call MPI_FILE_CLOSE(fh_vel(i), ierror)
                call MPI_FILE_CLOSE(fh_vel_b(i), ierror)
            enddo
        endif
        inquire(fh_nrho, opened=is_opened)
        if (is_opened) then
            call MPI_FILE_CLOSE(fh_nrho)
        endif
        inquire(fh_nrho_b, opened=is_opened)
        if (is_opened) then
            call MPI_FILE_CLOSE(fh_nrho_b)
        endif
    end subroutine close_velocity_density_files_b

    !---------------------------------------------------------------------------
    ! Read one-fluid velocities.
    ! Input:
    !   ct: current time frame.
    !---------------------------------------------------------------------------
    subroutine read_one_fluid_velocity(ct)
        use mpi_module
        use parameters, only: tp1
        use picinfo, only: domain, mime
        use mpi_io_module, only: read_data_mpi_io
        use mpi_datatype_fields, only: filetype_ghost, subsizes_ghost
        implicit none
        integer, intent(in) :: ct
        integer(kind=MPI_OFFSET_KIND) :: disp, offset

        disp = domain%nx * domain%ny * domain%nz * sizeof(MPI_REAL) * (ct-tp1)
        offset = 0
        call read_data_mpi_io(fh_vel(1), filetype_ghost, subsizes_ghost, &
            disp, offset, vsx)
        call read_data_mpi_io(fh_vel(2), filetype_ghost, subsizes_ghost, &
            disp, offset, vsy)
        call read_data_mpi_io(fh_vel(3), filetype_ghost, subsizes_ghost, &
            disp, offset, vsz)
    end subroutine read_one_fluid_velocity

    !---------------------------------------------------------------------------
    ! Read the velocity and density for the other species.
    ! Input:
    !   ct: current time frame.
    !   species: particle species. 'e' for electron. 'i' for ion.
    !---------------------------------------------------------------------------
    subroutine read_velocity_density_s(ct, species)
        use mpi_module
        use parameters, only: tp1
        use picinfo, only: domain, mime
        use mpi_io_module, only: read_data_mpi_io
        use mpi_datatype_fields, only: filetype_ghost, subsizes_ghost
        implicit none
        integer, intent(in) :: ct
        character(*), intent(in) :: species
        integer(kind=MPI_OFFSET_KIND) :: disp, offset

        disp = domain%nx * domain%ny * domain%nz * sizeof(MPI_REAL) * (ct-tp1)
        offset = 0
        call read_data_mpi_io(fh_vel(1), filetype_ghost, subsizes_ghost, &
            disp, offset, vsx)
        call read_data_mpi_io(fh_vel(2), filetype_ghost, subsizes_ghost, &
            disp, offset, vsy)
        call read_data_mpi_io(fh_vel(3), filetype_ghost, subsizes_ghost, &
            disp, offset, vsz)
        call read_data_mpi_io(fh_nrho, filetype_ghost, subsizes_ghost, &
            disp, offset, nrho_a)
    end subroutine read_velocity_density_s

    !---------------------------------------------------------------------------
    ! Read the velocity and density for both species.
    ! Input:
    !   ct: current time frame.
    !---------------------------------------------------------------------------
    subroutine read_velocity_density_b(ct)
        use mpi_module
        use parameters, only: tp1
        use picinfo, only: domain, mime
        use mpi_io_module, only: read_data_mpi_io
        use mpi_datatype_fields, only: filetype_ghost, subsizes_ghost
        implicit none
        integer, intent(in) :: ct
        integer(kind=MPI_OFFSET_KIND) :: disp, offset

        disp = domain%nx * domain%ny * domain%nz * sizeof(MPI_REAL) * (ct-tp1)
        offset = 0
        ! Electron
        call read_data_mpi_io(fh_vel(1), filetype_ghost, subsizes_ghost, &
            disp, offset, vsx)
        call read_data_mpi_io(fh_vel(2), filetype_ghost, subsizes_ghost, &
            disp, offset, vsy)
        call read_data_mpi_io(fh_vel(3), filetype_ghost, subsizes_ghost, &
            disp, offset, vsz)
        call read_data_mpi_io(fh_nrho, filetype_ghost, subsizes_ghost, &
            disp, offset, nrho_a)
        ! Ion
        call read_data_mpi_io(fh_vel_b(1), filetype_ghost, subsizes_ghost, &
            disp, offset, vx)
        call read_data_mpi_io(fh_vel_b(2), filetype_ghost, subsizes_ghost, &
            disp, offset, vy)
        call read_data_mpi_io(fh_vel_b(3), filetype_ghost, subsizes_ghost, &
            disp, offset, vz)
        call read_data_mpi_io(fh_nrho, filetype_ghost, subsizes_ghost, &
            disp, offset, nrho_b)
    end subroutine read_velocity_density_b

    !---------------------------------------------------------------------------
    ! Calculate the bulk flow velocity of single fluid, when the velocity is
    ! known for one species.
    !---------------------------------------------------------------------------
    subroutine calc_usingle_s(species)
        use picinfo, only: mime
        use pic_fields, only: vx, vy, vz, num_rho
        implicit none
        character(*), intent(in) :: species
        if (species == 'e') then
            vsx = (vsx*mime*nrho_a + vx*num_rho) / (num_rho + mime*nrho_a)
            vsy = (vsy*mime*nrho_a + vy*num_rho) / (num_rho + mime*nrho_a)
            vsz = (vsz*mime*nrho_a + vz*num_rho) / (num_rho + mime*nrho_a)
        else
            vsx = (vsx*nrho_a + vx*mime*num_rho) / (nrho_a + mime*num_rho)
            vsy = (vsy*nrho_a + vy*mime*num_rho) / (nrho_a + mime*num_rho)
            vsz = (vsz*nrho_a + vz*mime*num_rho) / (nrho_a + mime*num_rho)
        endif
    end subroutine calc_usingle_s

    !---------------------------------------------------------------------------
    ! Calculate the bulk flow velocity of single fluid, when the velocities are
    ! known for both species.
    !---------------------------------------------------------------------------
    subroutine calc_usingle_b
        use picinfo, only: mime
        implicit none
        vsx = (vsx*nrho_a + vx*mime*nrho_b) / (mime*nrho_b + nrho_a)
        vsy = (vsy*nrho_a + vy*mime*nrho_b) / (mime*nrho_b + nrho_a)
        vsz = (vsz*nrho_a + vz*mime*nrho_b) / (mime*nrho_b + nrho_a)
    end subroutine calc_usingle_b

end module usingle
