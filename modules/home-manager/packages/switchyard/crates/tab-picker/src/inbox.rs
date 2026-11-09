//! `rex-inbox`: the standalone rex-tab-picker on its Agents view, as the
//! old inbox's name. It runs the rex-tab-picker beside it under this name,
//! which main.rs reads.

use std::os::unix::process::CommandExt;

fn main() {
    let picker = std::env::current_exe()
        .map(|exe| exe.with_file_name("rex-tab-picker"))
        .unwrap_or_else(|_| "rex-tab-picker".into());
    let err = std::process::Command::new(picker).arg0("rex-inbox").args(std::env::args_os().skip(1)).exec();
    eprintln!("rex-inbox: can't run rex-tab-picker: {err}");
    std::process::exit(1);
}
