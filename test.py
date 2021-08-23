import math
from enum import Enum
import matplotlib.pyplot as plt
import numpy as np

show_animation = True


class RobotType(Enum):
    circle = 0
    rectangle = 1


class Config:
    def __init__(self):
        self.max_speed = 50.0  # [m/s]
        self.min_speed = 30.0  # [m/s]
        self.max_yaw_rate = 40.0 * math.pi / 180.0  # [rad/s]
        self.max_accel = 0.2  # [m/ss]
        self.max_delta_yaw_rate = 40.0 * math.pi / 180.0  # [rad/ss]
        self.v_resolution = 0.01  # [m/s]
        self.yaw_rate_resolution = 0.1 * math.pi / 180.0  # [rad/s]
        self.dt = 0.1  # [s] Time tick for motion prediction
        self.predict_time = 3.0  # [s]
        self.to_goal_cost_gain = 0.15
        self.speed_cost_gain = 1.0
        self.obstacle_cost_gain = 1.0
        self.robot_stuck_flag_cons = 0.001  # constant to prevent robot stucked
        self.robot_radius = 0.5  # [m] for collision check

        self.robot_width = 0.5
        self.robot_length = 1.2
        self.ob = np.array([[0, 2],
                [4.0, 2.0]
                ])
        

config = Config()


def dwa_control(x, config, goal, ob):
    dw = calc_dynamic_window(x, config)
    u, trajectory = calc_control_and_trajectory(x, dw, config, goal, ob)
    return u, trajectory


def motion(x, u, dt):
    x[2] += u[1] * dt
    x[0] += u[0] * math.cos(x[2]) * dt
    x[1] += u[0] * math.sin(x[2]) * dt
    x[3] = u[0]
    x[4] = u[1]

    return x


# Simple navigation
def calc_dynamic_window(x, config):
    # Dynamic window from robot specification
    Vs = [config.min_speed, config.max_speed,
          -config.max_yaw_rate, config.max_yaw_rate]

    # Dynamic window from motion model
    Vd = [x[3] - config.max_accel * config.dt,
          x[3] + config.max_accel * config.dt,
          x[4] - config.max_delta_yaw_rate * config.dt,
          x[4] + config.max_delta_yaw_rate * config.dt]

    #  [v_min, v_max, yaw_rate_min, yaw_rate_max]
    dw = [max(Vs[0], Vd[0]), min(Vs[1], Vd[1]),
          max(Vs[2], Vd[2]), min(Vs[3], Vd[3])]

    return dw


def predict_trajectory(x_init, v, y, config):
    x = np.array(x_init)
    trajectory = np.array(x)
    time = 0
    while time <= config.predict_time:
        x = motion(x, [v, y], config.dt)
        trajectory = np.vstack((trajectory, x))
        time += config.dt

    return trajectory


def calc_control_and_trajectory(x, dw, config, goal, ob):
    x_init = x[:]
    min_cost = float("inf")
    best_u = [0.0, 0.0]
    best_trajectory = np.array([x])

    # evaluate all trajectory with sampled input in dynamic window
    for v in np.arange(dw[0], dw[1], config.v_resolution):
        for y in np.arange(dw[2], dw[3], config.yaw_rate_resolution):

            trajectory = predict_trajectory(x_init, v, y, config)
            # calc cost
            to_goal_cost = config.to_goal_cost_gain * calc_to_goal_cost(trajectory, goal)
            speed_cost = config.speed_cost_gain * (config.max_speed - trajectory[-1, 3])
            ob_cost = config.obstacle_cost_gain * calc_obstacle_cost(trajectory, ob, config)

            final_cost = to_goal_cost + speed_cost + ob_cost

            # search minimum trajectory
            if min_cost >= final_cost:
                min_cost = final_cost
                best_u = [v, y]
                best_trajectory = trajectory
                if abs(best_u[0]) < config.robot_stuck_flag_cons \
                        and abs(x[3]) < config.robot_stuck_flag_cons:
                    best_u[1] = -config.max_delta_yaw_rate
    return best_u, best_trajectory


def calc_obstacle_cost(trajectory, ob, config):
    ox = ob[:, 0]
    oy = ob[:, 1]
    dx = trajectory[:, 0] - ox[:, None]
    dy = trajectory[:, 1] - oy[:, None]
    r = np.hypot(dx, dy)

    if np.array(r <= config.robot_radius).any():
        return float("Inf")

    min_r = np.min(r)
    return 1.0 / min_r  # OK


def calc_to_goal_cost(trajectory, goal):
    dx = goal[0] - trajectory[-1, 0]
    dy = goal[1] - trajectory[-1, 1]
    error_angle = math.atan2(dy, dx)
    cost_angle = error_angle - trajectory[-1, 2]
    cost = abs(math.atan2(math.sin(cost_angle), math.cos(cost_angle)))

    return cost


def plot_robot(x, y, yaw, config):  # pragma: no cover
    circle = plt.Circle((x, y), config.robot_radius, color="b")
    plt.gcf().gca().add_artist(circle)
    out_x, out_y = (np.array([x, y]) +
                    np.array([np.cos(yaw), np.sin(yaw)]) * config.robot_radius)
    plt.plot([x, out_x], [y, out_y], "-k")


class Map :
    def __init__(self, shape, obstacle) :
        self.ob = obstacle
        self.nrows = shape[0]
        self.ncols = shape[1]
        self.data = np.zeros(self.nrows*self.ncols)
        self.data = np.ma.array(self.data.reshape((self.nrows, self.ncols)), mask=self.data==0)

        self.test_colorize()
  
    def test_colorize(self) :
        self.data[3][2] = 50
        self.data[3][3] = 90
        self.data[3][4] = 50
        self.data[4][3] = 50
        self.data[2][3] = 50        
  
    def plot(self, predicted_trajectory,x,goal) :
        self.fig, self.ax = plt.subplots()
        self.ax.imshow(self.data, cmap="Greens", origin="lower", vmin=0)

        # optionally add grid
        self.ax.set_xticks(np.arange(self.ncols+1)-0.5, minor=True)
        self.ax.set_yticks(np.arange(self.nrows+1)-0.5, minor=True)
        self.ax.grid(which="minor")
        self.ax.tick_params(which="minor", size=0)
        plt.gcf().canvas.mpl_connect(
            'key_release_event',
            lambda event: [exit(0) if event.key == 'escape' else None])

        # Plot Informations
        plt.plot(predicted_trajectory[:, 0], predicted_trajectory[:, 1], "-g")
        plt.plot(x[0], x[1], "xr")
        plt.plot(goal[0], goal[1], "xb")
        plt.plot(self.ob[:, 0], self.ob[:, 1], "ok")
        plot_robot(x[0], x[1], x[2], config)
        plt.pause(3)



def main(gx=2.0, gy=1.5):
    print("start")

    # jesnk added below
    ob = config.ob
    map = Map((10,10), obstacle=ob)

    x = np.array([0.0, 0.0, math.pi / 8.0, 0.0, 0.0])
    goal = np.array([gx, gy])
    trajectory = np.array(x)
    
    while True:
        u, predicted_trajectory = dwa_control(x, config, goal, ob)
        x = motion(x, u, config.dt)  # simulate robot
        trajectory = np.vstack((trajectory, x))  # store state history

        # jesnk added below
        if show_animation :
            map.plot(predicted_trajectory,x,goal)

        '''
        # Prev show_animation
        if show_animation:
            plt.cla()
            # for stopping simulation with the esc key.
            plt.gcf().canvas.mpl_connect(
                'key_release_event',
                lambda event: [exit(0) if event.key == 'escape' else None])
            plt.plot(predicted_trajectory[:, 0], predicted_trajectory[:, 1], "-g")
            plt.plot(x[0], x[1], "xr")
            plt.plot(goal[0], goal[1], "xb")
            plt.plot(ob[:, 0], ob[:, 1], "ok")
            
            plot_robot(x[0], x[1], x[2], config)
            
            plt.axis("equal")
            #plt.grid(True)
            
            plt.pause(3)


        '''

        # check reaching goal
        dist_to_goal = math.hypot(x[0] - goal[0], x[1] - goal[1])
        if dist_to_goal <= config.robot_radius:
            print("Goal!!")
            break

    print("Done")
    if show_animation:
        plt.plot(trajectory[:, 0], trajectory[:, 1], "-r")
        plt.pause(3)

    plt.show()


if __name__ == '__main__':
    main()
