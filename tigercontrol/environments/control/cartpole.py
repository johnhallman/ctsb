"""
Non-PyBullet implementation of CartPole
"""
import jax
import jax.numpy as np
import jax.random as random

import tigercontrol
from tigercontrol.utils import generate_key
from tigercontrol.environments import Environment

# necessary for rendering
from gym.envs.classic_control import rendering


class CartPole(Environment):
    """
    Description:
        A pole is attached by an un-actuated joint to a cart, which moves along a frictionless track. 
        The pendulum starts upright, and the goal is to prevent it from falling over by increasing 
        and reducing the cart's velocity.
    """
    
    metadata = {
        'render.modes': ['human', 'rgb_array'],
        'video.frames_per_second' : 50
    }

    def get_loss(self):
        return self.L

    def __init__(self):
        self.initialized = False
        self.gravity = 9.8
        self.masscart = 1.0
        self.masspole = 0.1
        self.total_mass = (self.masspole + self.masscart)
        self.length = 0.5 # actually half the pole's length
        self.polemass_length = (self.masspole * self.length)
        self.force_mag = 10.0
        self.tau = 0.02  # seconds between state updates

        # Angle at which to fail the episode
        self.theta_threshold_radians = 15 * 2 * np.pi / 360
        self.x_threshold = 2.4

        self.action_space = (1,)
        self.observation_space = (4,)
        self.viewer = None
        self._state = None
        self.steps_beyond_done = None
        C_x, C_u = np.diag(np.array([0.1, 0.0, 1.0, 0.0])), np.diag(np.array([0.1]))
        L = lambda x, u: x.T @ C_x @ x + u.T @ C_u @ u
        self.L = jax.jit(L)


        def _dynamics(x_0, u): # dynamics
            x, x_dot, theta, theta_dot = np.split(x_0, 4)
            force = self.force_mag * np.clip(u, -1.0, 1.0)[0] # iLQR may struggle with clipping due to lack of gradient
            costh = np.cos(theta)
            sinth = np.sin(theta)
            temp = (force + self.polemass_length * theta_dot * theta_dot * sinth) / self.total_mass
            thetaacc = (self.gravity*sinth - costh*temp) / (self.length * (4.0/3.0 - self.masspole*costh*costh / self.total_mass))
            xacc  = temp - self.polemass_length * thetaacc * costh / self.total_mass
            x  = x + self.tau * x_dot # use euler integration by default
            x_dot = x_dot + self.tau * xacc
            theta = theta + self.tau * theta_dot
            theta_dot = theta_dot + self.tau * thetaacc
            state = np.concatenate((x, x_dot, theta, theta_dot))
            return state
        self._dynamics = jax.jit(_dynamics) # MUST store as self._dynamics for default rollout implementation to work
        C_x, C_u = (np.diag(np.array([0.2, 0.05, 1.0, 0.05])), np.diag(np.array([0.05])))
        self._loss = jax.jit(lambda x, u: x.T @ C_x @ x + u.T @ C_u @ u) # MUST store as self._loss

    def initialize(self):
        """ Initialize or reset the CartPole environment """
        self.initialized = True
        return self._reset()

    def step(self, action):
        """ Description: updates internal state <- dynamcics(state, action) and returns state, cost, and done boolean """
        assert self.initialized
        if type(action) == np.ndarray: action = action[0]
        old_state = self._state
        self._state = self._dynamics(self._state, action)
        x, theta = self._state[0], self._state[2]
        x_lim, th_lim = self.x_threshold, self.theta_threshold_radians
        done = bool(x < -x_lim or x > x_lim or theta < -th_lim or theta > th_lim)
        cost = self._loss(old_state)
        return self._state, cost, done

    def _reset(self):
        """ Description: Reset the environment and return the start state """
        self._state = random.uniform(generate_key(),shape=(4,), minval=-0.05, maxval=0.05)
        self.steps_beyond_done = None
        # self._state = np.array([0.0, 0.03, 0.03, 0.03]) # reproducible results
        return self._state

    def render(self, mode='human'):
        """ Description: Renders on screen an image of the current cartpole state """
        screen_width = 600
        screen_height = 400

        world_width = self.x_threshold*2
        scale = screen_width/world_width
        carty = 100 # TOP OF CART
        polewidth = 10.0
        polelen = scale * (2 * self.length)
        cartwidth = 50.0
        cartheight = 30.0

        if self.viewer is None:
            self.viewer = rendering.Viewer(screen_width, screen_height)
            l,r,t,b = -cartwidth/2, cartwidth/2, cartheight/2, -cartheight/2
            axleoffset =cartheight/4.0
            cart = rendering.FilledPolygon([(l,b), (l,t), (r,t), (r,b)])
            self.carttrans = rendering.Transform()
            cart.add_attr(self.carttrans)
            self.viewer.add_geom(cart)
            l,r,t,b = -polewidth/2,polewidth/2,polelen-polewidth/2,-polewidth/2
            pole = rendering.FilledPolygon([(l,b), (l,t), (r,t), (r,b)])
            pole.set_color(.8,.6,.4)
            self.poletrans = rendering.Transform(translation=(0, axleoffset))
            pole.add_attr(self.poletrans)
            pole.add_attr(self.carttrans)
            self.viewer.add_geom(pole)
            self.axle = rendering.make_circle(polewidth/2)
            self.axle.add_attr(self.poletrans)
            self.axle.add_attr(self.carttrans)
            self.axle.set_color(.5,.5,.8)
            self.viewer.add_geom(self.axle)
            self.track = rendering.Line((0,carty), (screen_width,carty))
            self.track.set_color(0,0,0)
            self.viewer.add_geom(self.track)
            self._pole_geom = pole
        if self._state is None: return None

        # Edit the pole polygon vertex
        pole = self._pole_geom
        l,r,t,b = -polewidth/2,polewidth/2,polelen-polewidth/2,-polewidth/2
        pole.v = [(l,b), (l,t), (r,t), (r,b)]
        x = self._state
        cartx = x[0]*scale+screen_width/2.0 # MIDDLE OF CART
        self.carttrans.set_translation(cartx, carty)
        self.poletrans.set_rotation(-x[2])
        return self.viewer.render(return_rgb_array = mode=='rgb_array')

    def close(self):
        """ Description: Close the environment and return memory """
        if self.viewer:
            self.viewer.close()
            self.viewer = None



