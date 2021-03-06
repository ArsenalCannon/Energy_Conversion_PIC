!*******************************************************************************
! Flags for whether save one kind of calculated field. 0 for not. 1 for yes.
! This is for saving large 2D or 3D data.
!*******************************************************************************
module saving_flags
    implicit none
    private
    public save_jcpara, save_jcperp, save_jmag, save_jgrad, save_jdiagm, &
           save_jpolar, save_jexb, save_jpara, save_jperp, save_jperp1, &
           save_jperp2, save_jqnvpara, save_jqnvperp, save_jagy, save_jtot, &
           save_jdivv, save_pre, &
           save_jcpara_dote, save_jcperp_dote, save_jmag_dote, save_jgrad_dote, &
           save_jdiagm_dote, save_jpolar_dote, save_jexb_dote, save_jpara_dote, &
           save_jperp_dote, save_jperp1_dote, save_jperp2_dote, &
           save_jqnvpara_dote, save_jqnvperp_dote, save_jagy_dote, &
           save_jtot_dote, save_jdivv_dote
    public get_saving_flags

    integer :: save_jcpara, save_jcperp, save_jmag
    integer :: save_jgrad, save_jdiagm, save_jpolar
    integer :: save_jexb, save_jpara, save_jperp
    integer :: save_jperp1, save_jperp2, save_jqnvpara
    integer :: save_jqnvperp, save_jagy, save_jtot, save_jdivv
    integer :: save_jcpara_dote, save_jcperp_dote, save_jmag_dote
    integer :: save_jgrad_dote, save_jdiagm_dote, save_jpolar_dote
    integer :: save_jexb_dote, save_jpara_dote, save_jperp_dote
    integer :: save_jperp1_dote, save_jperp2_dote, save_jqnvpara_dote
    integer :: save_jqnvperp_dote, save_jagy_dote, save_jtot_dote, save_jdivv_dote
    integer :: save_pre

    contains

    !---------------------------------------------------------------------------
    ! Read the saving flags from configuration file.
    !---------------------------------------------------------------------------
    subroutine get_saving_flags
        use read_config, only: get_variable_int
        implicit none
        integer :: fh
        fh = 15
        open(unit=fh, file='config_files/saving_flags.dat', status='old')
        save_jcpara = get_variable_int(fh, 'save_jcpara', '=')
        save_jcperp = get_variable_int(fh, 'save_jcperp', '=')
        save_jmag = get_variable_int(fh, 'save_jmag', '=')
        save_jgrad = get_variable_int(fh, 'save_jgrad', '=')
        save_jdiagm = get_variable_int(fh, 'save_jdiagm', '=')
        save_jpolar = get_variable_int(fh, 'save_jpolar', '=')
        save_jexb = get_variable_int(fh, 'save_jexb', '=')
        save_jpara = get_variable_int(fh, 'save_jpara', '=')
        save_jperp = get_variable_int(fh, 'save_jperp', '=')
        save_jperp1 = get_variable_int(fh, 'save_jperp1', '=')
        save_jperp2 = get_variable_int(fh, 'save_jperp2', '=')
        save_jqnvpara = get_variable_int(fh, 'save_jqnvpara', '=')
        save_jqnvperp = get_variable_int(fh, 'save_jqnvperp', '=')
        save_jagy = get_variable_int(fh, 'save_jagy', '=')
        save_jtot = get_variable_int(fh, 'save_jtot', '=')
        save_jtot = get_variable_int(fh, 'save_jdivv', '=')
        save_pre = get_variable_int(fh, 'save_pre', '=')
        save_jcpara_dote = get_variable_int(fh, 'save_jcpara_dote', '=')
        save_jcperp_dote = get_variable_int(fh, 'save_jcperp_dote', '=')
        save_jmag_dote = get_variable_int(fh, 'save_jmag_dote', '=')
        save_jgrad_dote = get_variable_int(fh, 'save_jgrad_dote', '=')
        save_jdiagm_dote = get_variable_int(fh, 'save_jdiagm_dote', '=')
        save_jpolar_dote = get_variable_int(fh, 'save_jpolar_dote', '=')
        save_jexb_dote = get_variable_int(fh, 'save_jexb_dote', '=')
        save_jpara_dote = get_variable_int(fh, 'save_jpara_dote', '=')
        save_jperp_dote = get_variable_int(fh, 'save_jperp_dote', '=')
        save_jperp1_dote = get_variable_int(fh, 'save_jperp1_dote', '=')
        save_jperp2_dote = get_variable_int(fh, 'save_jperp2_dote', '=')
        save_jqnvpara_dote = get_variable_int(fh, 'save_jqnvpara_dote', '=')
        save_jqnvperp_dote = get_variable_int(fh, 'save_jqnvperp_dote', '=')
        save_jagy_dote = get_variable_int(fh, 'save_jagy_dote', '=')
        save_jtot_dote = get_variable_int(fh, 'save_jtot_dote', '=')
        save_jtot_dote = get_variable_int(fh, 'save_jdivv_dote', '=')
        close(fh)
    end subroutine get_saving_flags

end module saving_flags
