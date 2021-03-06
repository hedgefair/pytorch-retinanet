'''RetinaFPN in PyTorch.'''
import torch
import torch.nn as nn
import torch.nn.functional as F

from torch.autograd import Variable


class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, in_planes, planes, stride=1):
        super(Bottleneck, self).__init__()
        self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.conv3 = nn.Conv2d(planes, self.expansion*planes, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(self.expansion*planes)

        self.shortcut = nn.Sequential()
        if stride != 1 or in_planes != self.expansion*planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_planes, self.expansion*planes, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(self.expansion*planes)
            )

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = F.relu(self.bn2(self.conv2(out)))
        out = self.bn3(self.conv3(out))
        out += self.shortcut(x)
        out = F.relu(out)
        return out


class RetinaFPN(nn.Module):
    def __init__(self, block, num_blocks):
        super(RetinaFPN, self).__init__()
        self.in_planes = 64

        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)

        # Bottom-up layers
        self.layer2 = self._make_layer(block,  64, num_blocks[0], stride=1)
        self.layer3 = self._make_layer(block, 128, num_blocks[1], stride=2)
        self.layer4 = self._make_layer(block, 256, num_blocks[2], stride=2)
        self.layer5 = self._make_layer(block, 512, num_blocks[3], stride=2)
        self.conv6 = nn.Conv2d(2048, 256, kernel_size=3, stride=2, padding=1)
        self.conv7 = nn.Conv2d( 256, 256, kernel_size=3, stride=2, padding=1)

        # TODO: merge toplayer1 & conv6?
        self.toplayer1 = nn.Conv2d(2048, 256, kernel_size=1, stride=1, padding=0)  # Reduce channels
        self.toplayer2 = nn.Conv2d( 256, 256, kernel_size=3, stride=1, padding=1)
        self.toplayer3 = nn.Conv2d( 256, 256, kernel_size=3, stride=1, padding=1)

        # Lateral layers
        self.latlayer1 = nn.Conv2d(1024, 256, kernel_size=1, stride=1, padding=0)
        self.latlayer2 = nn.Conv2d( 512, 256, kernel_size=1, stride=1, padding=0)

    def _make_layer(self, block, planes, num_blocks, stride):
        strides = [stride] + [1]*(num_blocks-1)
        layers = []
        for stride in strides:
            layers.append(block(self.in_planes, planes, stride))
            self.in_planes = planes * block.expansion
        return nn.Sequential(*layers)

    def _add(self, x, y):
        '''Add two feature maps.

        Args:
          x: (Variable) upsampled feature map.
          y: (Variable) lateral feature map.

        Returns:
          (Variable) added feature map.

        Upsampled feature map size is always >= lateral feature map size.
        The reason why the two feature map sizes may not equal is because when the
        input size is odd, the upsampled feature map size is always 1 pixel
        bigger than the original input size.

        e.g.
        original input size: [N,_,15,15] ->
        conv2d feature map size: [N,_,8,8] ->
        upsamped feature map size: [N,_,16,16]
        '''
        _,_,H,W = y.size()
        return x[:,:,:H,:W] + y

    def forward(self, x):
        # Bottom-up
        c1 = F.relu(self.bn1(self.conv1(x)))
        c1 = F.max_pool2d(c1, kernel_size=3, stride=2, padding=1)
        c2 = self.layer2(c1)
        c3 = self.layer3(c2)
        c4 = self.layer4(c3)
        c5 = self.layer5(c4)
        p6 = self.conv6(c5)
        p7 = self.conv7(F.relu(p6))
        # Top-down
        p5 = self.toplayer1(c5)
        p4 = self._add(F.upsample(p5, scale_factor=2), self.latlayer1(c4))
        p4 = self.toplayer2(p4)
        p3 = self._add(F.upsample(p4, scale_factor=2), self.latlayer2(c3))
        p3 = self.toplayer3(p3)
        return p3, p4, p5, p6, p7


def RetinaFPN50():
    return RetinaFPN(Bottleneck, [3,4,6,3])

def RetinaFPN101():
    return RetinaFPN(Bottleneck, [2,4,23,3])


def test():
    net = RetinaFPN101()
    fms = net(Variable(torch.randn(1,3,600,300)))
    for fm in fms:
        print(fm.size())

# test()
