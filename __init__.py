import sys
import time
from a_pandas_ex_apply_ignore_exceptions import pd_add_apply_ignore_exceptions
import pandas as pd
from pandasxmledit import PandasXMLEdit
from usefuladb import AdbCommands
import regex
from a_pandas_ex_less_memory_more_speed import pd_add_less_memory_more_speed
pd_add_less_memory_more_speed()
pd_add_apply_ignore_exceptions()
num_pattern = regex.compile(r"\b\d+\b", flags=regex.I)


class Tap:
    def __init__(self, fu, x, y, use_time=True, t=1):
        self.x = x
        self.y = y
        self.px = str(x).rjust(4)
        self.py = str(y).rjust(4)
        self.t = t
        self.use_time = use_time
        self.fu = fu

    def __str__(self):
        if self.use_time:
            return f"x:{self.px} y:{self.py} t:{self.t}"
        else:
            return f"x:{self.px} y:{self.py}"

    def __repr__(self):
        return self.__str__()

    def __call__(self, *args, **kwargs):
        ti = None
        if self.use_time:
            ti = args[0] if args else self.t
        if ti:
            return self.fu(self.x, self.y, ti)
        else:
            return self.fu(self.x, self.y)


true_false_convert = [
    "cc_checkable",
    "cc_checked",
    "cc_clickable",
    "cc_enabled",
    "cc_focusable",
    "cc_focused",
    "cc_scrollable",
    "cc_long_clickable",
    "cc_password",
    "cc_selected",
]

methods_to_add = [
    "sh_input_dpad_longtap",
    "sh_input_dpad_tap",
    "sh_input_gamepad_longtap",
    "sh_input_gamepad_tap",
    "sh_input_joystick_longtap",
    "sh_input_joystick_tap",
    "sh_input_keyboard_longtap",
    "sh_input_keyboard_tap",
    "sh_input_mouse_longtap",
    "sh_input_mouse_tap",
    "sh_input_stylus_longtap",
    "sh_input_stylus_tap",
    "sh_input_tap",
    "sh_input_touchnavigation_longtap",
    "sh_input_touchnavigation_tap",
    "sh_input_touchpad_longtap",
    "sh_input_touchpad_tap",
    "sh_input_touchscreen_longtap",
    "sh_input_touchscreen_tap",
    "sh_input_trackball_longtap",
    "sh_input_trackball_tap",
]


def get_uiautomatordf(
    adbc,
    timeout=60,
    remove_old_file=True,
    with_fu=True,
    tmpfile="/sdcard/view.xml",
    sleep_after_dump=0.05,
    t_long_touch=1,
    **kwargs,
):
    def _get_uiautomatordf():
        adbc.execute_sh_command(f"uiautomator dump {tmpfile}", **kwargs)
        time.sleep(sleep_after_dump)
        uidu = adbc.sh_cat_get_file(tmpfile, **kwargs)

        df2 = PandasXMLEdit(
            xmldata=uidu,
            convert_dtypes=False,
            process_namespaces=False,
        ).df

        allk = []
        df2collist = df2.columns[:-1].to_list()
        for key, item in df2.iterrows():
            likey = []
            for col in df2collist:
                v2 = item[col]
                if pd.isna(v2):
                    break
                else:
                    likey.append(v2)
            val = item["value"]
            allk.append([tuple(likey), tuple(likey[:-1]), likey[-1], val])
        df3 = pd.DataFrame(allk)

        joinedgr = []
        for name, group in df3.groupby(1):
            group2 = group.set_index(2).drop(columns=[0, 1]).T.reset_index(drop=True)
            group2["cc_hierarchy"] = [group[1].iloc[0]]
            group2.columns = [
                str(x).replace("@", "cc_").replace("-", "_") for x in group2.columns
            ]
            joinedgr.append(group2)

        df4 = pd.concat(joinedgr, ignore_index=True)
        df4 = (
            df4.loc[df4.cc_rotation.isna()]
            .reset_index(drop=True)
            .dropna(axis=1, how="all")
        )
        try:
            df4.cc_hierarchy = df4.cc_hierarchy.str[1:]
        except Exception:
            pass
        for co in true_false_convert:
            if co in df4.columns:
                df4[co].replace({"true": True, "false": False}, inplace=True)

        df4 = (
            pd.concat(
                [
                    df4,
                    df4.cc_bounds.ds_apply_ignore(
                        [pd.NA, pd.NA, pd.NA, pd.NA],
                        lambda x: [int(h) for h in num_pattern.findall(x)],
                    )
                    .apply(pd.Series)
                    .rename(
                        columns={
                            0: "cc_start_x",
                            1: "cc_start_y",
                            2: "cc_end_x",
                            3: "cc_end_y",
                        }
                    ),
                ],
                axis=1,
            )
            .dropna(subset=["cc_start_x", "cc_start_y", "cc_end_x", "cc_end_y"])
            .reset_index(drop=True)
        )

        df4["cc_width"] = df4["cc_end_x"] - df4["cc_start_x"]
        df4["cc_height"] = df4["cc_end_y"] - df4["cc_start_y"]
        df4["cc_center_x"] = (df4["cc_start_x"] + df4["cc_end_x"]) // 2
        df4["cc_center_y"] = (df4["cc_start_y"] + df4["cc_end_y"]) // 2
        df4["cc_area"] = df4["cc_width"] * df4["cc_height"]
        df4 = df4.drop(columns=["cc_bounds"]).ds_reduce_memory_size_carefully(
            verbose=False
        )
        if with_fu:
            for m in methods_to_add:
                m_co = "ff_" + m[9:]
                df4.loc[:, m_co] = df4.ds_apply_ignore(
                    pd.NA,
                    lambda q: Tap(
                        getattr(adbc, m),
                        q.cc_center_x,
                        q.cc_center_y,
                        True if m_co.endswith("_longtap") else False,
                        t_long_touch,
                    ),
                    axis=1,
                )
        return df4

    if remove_old_file:
        adbc.sh_remove_file(tmpfile)
    finaltimeout = time.time() + timeout
    while time.time() < finaltimeout:
        try:
            return _get_uiautomatordf()
        except Exception as fe:
            sys.stderr.write(f"{fe}\n")
    return pd.DataFrame()


class UiAutoDumpLite:
    def __init__(self, adb=None, adb_path=None, serial_number=None, **kwargs):
        r"""
        UiAutoDumpLite is a class for interacting with the UIAutomator tool to retrieve UI information
        from an Android device using ADB (Android Debug Bridge).

        Parameters:
            adb (AdbCommands, optional): An instance of AdbCommands for executing ADB commands.
            adb_path (str, optional): The path to the ADB executable. If not provided, it will use the
                system's ADB if available.
            serial_number (str, optional): The serial number of the Android device to target when using ADB.
            **kwargs: Additional keyword arguments to pass to AdbCommands.

        Methods:
            get_df(timeout=60, remove_old_file=True, with_fu=True, tmpfile="/sdcard/view.xml",
                   sleep_after_dump=0.05, t_long_touch=1, **kwargs):
            - Retrieves UI information from the Android device and returns it as a DataFrame.

        Example usage:
            adb_path = r"C:\Android\android-sdk\platform-tools\adb.exe"
            serial_number = "127.0.0.1:5555"
            uadb = AdbCommands(adb_path, serial_number, use_busybox=False)

            # Create UiAutoDumpLite instances
            dfg1 = UiAutoDumpLite(adb_path=adb_path, serial_number=serial_number)
            dfg2 = UiAutoDumpLite(adb=uadb)

            # Get UI information DataFrame
            df = dfg1.get_df(
                timeout=60,
                remove_old_file=True,
                with_fu=True,
                tmpfile="/sdcard/view.xml",
                sleep_after_dump=0.05,
                t_long_touch=1,
            )
        """
        if not adb:
            self.adb = AdbCommands(adb_path, serial_number, **kwargs)
        else:
            self.adb = adb

    def __str__(self):
        return self.adb.device_serial

    def __repr__(self):
        return self.adb.device_serial

    def get_df(
        self,
        timeout=60,
        remove_old_file=True,
        with_fu=True,
        tmpfile="/sdcard/view.xml",
        sleep_after_dump=0.05,
        t_long_touch=1,
        **kwargs,
    ):
        r"""
        Retrieve UI information from the Android device and return it as a DataFrame.

        Parameters:
            timeout (int, optional): The maximum time to wait for UI information retrieval, in seconds.
            remove_old_file (bool, optional): Whether to remove the old UI information file before dumping a new one.
            with_fu (bool, optional): Whether to include Tap objects for interaction in the DataFrame.
            tmpfile (str, optional): The path to the temporary UI information file on the Android device.
            sleep_after_dump (float, optional): Time to sleep after dumping UI information.
            t_long_touch (int, optional): Duration for long-touch actions.
            **kwargs: Additional keyword arguments to pass to AdbCommands.

        Returns:
            pandas.DataFrame: A DataFrame containing UI information.
        """
        return get_uiautomatordf(
            self.adb,
            timeout=timeout,
            remove_old_file=remove_old_file,
            with_fu=with_fu,
            tmpfile=tmpfile,
            sleep_after_dump=sleep_after_dump,
            t_long_touch=t_long_touch,**kwargs,
        )

