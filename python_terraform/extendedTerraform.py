import subprocess
import sys
import os
import logging
import tempfile
from python_terraform.terraform import Terraform, TerraformCommandError

logger = logging.getLogger(__name__)


class ExtendedTerraform(Terraform):
    def cmd(
        self,
        cmd,
        *args,
        capture_output=None,
        raise_on_error=True,
        synchronous=True,
        **kwargs,
    ):
        if capture_output is True:
            stderr = subprocess.PIPE
            stdout = subprocess.PIPE
        elif capture_output == "framework":
            stderr = None
            stdout = None
        else:
            stderr = subprocess.PIPE
            stdout = sys.stdout

        cmds = self.generate_cmd_string(cmd, *args, **kwargs)
        logger.info("Command: %s", " ".join(cmds))

        working_folder = self.working_dir if self.working_dir else None

        environ_vars = {}
        if self.is_env_vars_included:
            environ_vars = os.environ.copy()

        with tempfile.NamedTemporaryFile(delete=False) as temp_log_file:
            temp_log_path = temp_log_file.name
            p = subprocess.Popen(
                cmds,
                stdout=stdout,
                stderr=subprocess.PIPE,
                cwd=working_folder,
                env=environ_vars,
            )

            if not synchronous:
                return None, None, None

            out = []
            err = []
            for line in iter(p.stdout.readline, b""):
                line_decoded = line.decode()
                sys.stderr.write(line_decoded)  # Write directly to stderr
                temp_log_file.write(
                    f"[SG_ERROR] {line_decoded}".encode()
                )  # Write to temp file with prefix
                err.append(line_decoded)

            p.stdout.close()
            p.wait()
            ret_code = p.returncode

        if ret_code == 0:
            self.read_state_file()
        else:
            logger.warning("Command returned with error code: %s", ret_code)
            with open(temp_log_path, "r") as log_file:
                print(log_file.read())  # Print the content of the temp log file

        self.temp_var_files.clean_up()

        out = None
        err = "".join(err) if capture_output is True else None

        if ret_code and raise_on_error:
            raise TerraformCommandError(ret_code, " ".join(cmds), out=out, err=err)

        return ret_code, out, err
