import os
import argparse
from re import I
import time
import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim

parser = argparse.ArgumentParser('ODE demo')
parser.add_argument('--method', type=str, choices=['dopri5', 'adams'], default='dopri5')
parser.add_argument('--data_size', type=int, default=1000)
parser.add_argument('--batch_time', type=int, default=10)
parser.add_argument('--batch_size', type=int, default=20)
parser.add_argument('--niters', type=int, default=2000)
parser.add_argument('--test_freq', type=int, default=20)
parser.add_argument('--viz', action='store_true')
parser.add_argument('--vecfield', action='store_true')
parser.add_argument('--gpu', type=int, default=0)
parser.add_argument('--adjoint', action='store_true')
args = parser.parse_args()

if args.adjoint:
    from torchdiffeq import odeint_adjoint as odeint
else:
    from torchdiffeq import odeint

device = torch.device('cuda:' + str(args.gpu) if torch.cuda.is_available() else 'cpu')

t = torch.linspace(0., 20., args.data_size).to(device)
# 2D Spiral
# true_y0 = torch.tensor([[2., 0.]]).to(device)
# true_A = torch.tensor([[-0.1, 2.0], [-2.0, -0.1]]).to(device)

# Volterra-Lotka System
# true_y0 = torch.tensor([[2., 0.]]).to(device)
# a, b, c, d = 1.5, 1.0, 3.0, 1.0
# true_A = torch.tensor([[0., -b*c/d], [d*a/b, 0.]])

# 3D Spiral
# true_y0 = torch.tensor([[0., 1., 0.]]).to(device)
true_y = []

# for curr_t in t:
#   true_y.append([[torch.sin(torch.pi * curr_t), torch.cos(torch.pi * curr_t), curr_t]])

# Expanding 3D spiral
# true_y0 = torch.tensor([[0., 0., 0.]]).to(device)
# for curr_t in t:
#   true_y.append([[curr_t * torch.sin(torch.pi * curr_t) / 10, curr_t * torch.cos(torch.pi * curr_t) / 10, curr_t]])

# Ellipse
true_y0 = torch.tensor([[1., 0., 3.]]).to(device)
for curr_t in t:
  true_y.append([[torch.cos(torch.pi * curr_t), 2 * torch.sin(torch.pi * curr_t), 3]])

true_y = torch.tensor(true_y)

def get_batch():
    s = torch.from_numpy(np.random.choice(np.arange(args.data_size - args.batch_time, dtype=np.int64), args.batch_size, replace=False))
    batch_y0 = true_y[s]  # (M, D)
    batch_t = t[:args.batch_time]  # (T)
    batch_y = torch.stack([true_y[s + i] for i in range(args.batch_time)], dim=0)  # (T, M, D)
    return batch_y0.to(device), batch_t.to(device), batch_y.to(device)


def makedirs(dirname):
    if not os.path.exists(dirname):
        os.makedirs(dirname)


if args.viz:
    makedirs('png')
    import matplotlib.pyplot as plt
    from mpl_toolkits import mplot3d
    fig = plt.figure(figsize=(12, 4), facecolor='white')
    ax_traj = fig.add_subplot(131, frameon=False)
    ax_phase = fig.add_subplot(132, projection='3d')
    if (args.vecfield):
        ax_vecfield = fig.add_subplot(133, projection='3d')
    plt.show(block=False)


def visualize(true_y, pred_y, odefunc, itr):

    if args.viz:

        ax_traj.cla()
        ax_traj.set_title('Trajectories')
        ax_traj.set_xlabel('t')
        ax_traj.set_ylabel('x,y,z')
        ax_traj.plot(t.cpu().numpy(), true_y.cpu().numpy()[:, 0, 0], t.cpu().numpy(), true_y.cpu().numpy()[:, 0, 1], t.cpu().numpy(), true_y.cpu().numpy()[:, 0, 2], 'g-')
        ax_traj.plot(t.cpu().numpy(), pred_y.cpu().numpy()[:, 0, 0], '--', t.cpu().numpy(), pred_y.cpu().numpy()[:, 0, 1], t.cpu().numpy(), pred_y.cpu().numpy()[:, 0, 2], 'b--')
        ax_traj.set_xlim(t.cpu().min(), t.cpu().max())
        ax_traj.set_ylim(-2, 2)
        ax_traj.legend()

        ax_phase.cla()
        ax_phase.set_title('Phase Portrait')
        ax_phase.set_xlabel('x')
        ax_phase.set_ylabel('y')
        ax_phase.set_zlabel('z')
        ax_phase.plot(true_y.cpu().numpy()[:, 0, 0], true_y.cpu().numpy()[:, 0, 1], true_y.cpu().numpy()[:, 0, 2], 'g-')
        ax_phase.plot(pred_y.cpu().numpy()[:, 0, 0], pred_y.cpu().numpy()[:, 0, 1], pred_y.cpu().numpy()[:, 0, 2], 'b--')
        ax_phase.set_xlim(-2, 2)
        ax_phase.set_ylim(-2, 2)
        ax_phase.set_zlim(0, 20)

        if (args.vecfield):
            ax_vecfield.cla()
            ax_vecfield.set_title('Learned Vector Field')
            ax_vecfield.set_xlabel('x')
            ax_vecfield.set_ylabel('y')
            ax_vecfield.set_zlabel('z')

            z, y, x = np.mgrid[0:20:21j, -2:2:21j, -2:2:21j]
            dydt = odefunc(0, torch.Tensor(np.stack([x, y, z], -1).reshape(21 * 21 * 21, 3)).to(device)).cpu().detach().numpy()
            mag = np.sqrt(dydt[:, 0]**2 + dydt[:, 1]**2 + dydt[:, 2]**2).reshape(-1, 1)
            dydt = (dydt / mag)
            dydt = dydt.reshape(21, 21, 21, 3)

            widths = np.linspace(0, 0.1, x.size)
            ax_vecfield.quiver(x, y, z, dydt[:, :, :, 0], dydt[:, :, :, 1], dydt[:, :, :, 2], linewidths=widths, color="black")
            ax_vecfield.set_xlim(-2, 2)
            ax_vecfield.set_ylim(-2, 2)
            ax_vecfield.set_zlim(0, 20)

        fig.tight_layout()
        plt.savefig('png/{:03d}'.format(itr))
        plt.draw()
        plt.pause(0.001)


class ODEFunc(nn.Module):

    def __init__(self):
        super(ODEFunc, self).__init__()

        # 2D net
        # self.net = nn.Sequential(
        #     nn.Linear(2, 50),
        #     nn.Tanh(),
        #     nn.Linear(50, 2),
        # )

        # 3D net
        self.net = nn.Sequential(
            nn.Linear(3, 50),
            nn.Tanh(),
            nn.Linear(50, 3),
        )

        # Large 3D net
        # self.net = nn.Sequential(
        #     nn.Linear(3, 50),
        #     nn.Tanh(),
        #     nn.Linear(50, 150),
        #     nn.Tanh(),
        #     nn.Linear(150, 50),
        #     nn.Tanh(),
        #     nn.Linear(50, 3),
        # )

        for m in self.net.modules():
            if isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, mean=0, std=0.1)
                nn.init.constant_(m.bias, val=0)

    def forward(self, t, y):
        return self.net(y)


class RunningAverageMeter(object):
    """Computes and stores the average and current value"""

    def __init__(self, momentum=0.99):
        self.momentum = momentum
        self.reset()

    def reset(self):
        self.val = None
        self.avg = 0

    def update(self, val):
        if self.val is None:
            self.avg = val
        else:
            self.avg = self.avg * self.momentum + val * (1 - self.momentum)
        self.val = val


if __name__ == '__main__':

    ii = 0

    func = ODEFunc().to(device)
    
    optimizer = optim.RMSprop(func.parameters(), lr=1e-3)
    end = time.time()

    time_meter = RunningAverageMeter(0.97)
    
    loss_meter = RunningAverageMeter(0.97)

    for itr in range(1, args.niters + 1):
        optimizer.zero_grad()
        batch_y0, batch_t, batch_y = get_batch()
        pred_y = odeint(func, batch_y0, batch_t).to(device)
        loss = torch.mean(torch.abs(pred_y - batch_y))
        loss.backward()
        optimizer.step()

        time_meter.update(time.time() - end)
        loss_meter.update(loss.item())

        if itr % args.test_freq == 0:
            with torch.no_grad():
                pred_y = odeint(func, true_y0, t)
                loss = torch.mean(torch.abs(pred_y - true_y))
                print('Iter {:04d} | Total Loss {:.6f}'.format(itr, loss.item()))
                visualize(true_y, pred_y, func, ii)
                ii += 1

        end = time.time()