import time


class FPSCounter:
    def __init__(self, start_when_init=True, fps_print_cycle=None, prefix_fps_print=""):
        """
        Initializes the FPSCounter instance.

        Args:
            start_when_init (bool): Whether to start counting FPS immediately upon initialization.
            fps_print_cycle (float or None): The interval (in seconds) at which FPS will be printed.
            prefix_fps_print (str): A prefix string to include in the FPS print statement.
        """
        self.start_time = None
        self.total_frames = 0
        self.last_print_time = None
        self.fps_print_cycle = fps_print_cycle
        self.prefix_fps_print = prefix_fps_print
        if start_when_init:
            self.start()

    def start(self):
        """
        Resets the FPS counter and starts the time tracking.

        Initializes the start time and sets the total frame count to 0.
        """
        self.start_time = time.time()
        self.last_print_time = self.start_time
        self.total_frames = 0

    def update(self):
        """
        Updates the FPS counter by incrementing the frame count and optionally printing the FPS.

        If the frame count exceeds 1,000,000, the counter is reset.
        If `fps_print_cycle` is set, the FPS is printed at the specified interval.
        """
        if self.total_frames > 1_000_000:
            self.start()
        else:
            self.total_frames += 1

        if self.fps_print_cycle is not None:
            elapsed_time = time.time() - self.last_print_time
            if elapsed_time >= self.fps_print_cycle:
                print(f"{self.prefix_fps_print} FPS: {int(self.get_fps())}")
                self.start()

    def get_fps(self):
        """
        Get the current FPS (frames per second).

        Calculates FPS as the total number of frames divided by the elapsed time.

        Returns:
            float: The calculated FPS, or 0 if the counter has not started.
        """
        if self.start_time is None:
            return 0
        elapsed_time = time.time() - self.start_time
        if elapsed_time == 0:
            return 0
        fps = self.total_frames / elapsed_time
        return fps

    def keep_target_fps(self, target_fps):
        """
        Ensure the FPS stays below or at the target FPS by adjusting the sleep time.

        Args:
            target_fps (float): The target FPS to maintain.
        """
        current_fps = self.get_fps()
        if current_fps > target_fps:
            sleep_time = self.total_frames / target_fps - (
                time.time() - self.start_time
            )
            if sleep_time > 0:
                time.sleep(sleep_time)
