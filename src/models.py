from torch import nn
import torch


class UNetDown(nn.Module):
    def __init__(self, in_size, out_size, normalize=True, dropout=0.0):
        super(UNetDown, self).__init__()
        layers = [nn.Conv2d(in_size, out_size, 4, 2, 1, bias=True),
                  nn.BatchNorm2d(out_size, momentum=0.8),
                  nn.LeakyReLU(0.2)]

        # if dropout:
        #    layers.append(nn.Dropout(dropout))
        self.model = nn.Sequential(*layers)

    def forward(self, x):
        return self.model(x)


class UNetUp(nn.Module):
    def __init__(self, in_size, out_size, dropout=0.0):
        super(UNetUp, self).__init__()
        layers = [
            nn.ConvTranspose2d(in_size, out_size, 4, 2, 1, bias=True),
            nn.Conv2d(out_size, out_size, 3, 1, 1),  # ???
            nn.BatchNorm2d(out_size, momentum=0.8),
            nn.LeakyReLU(inplace=True)]
        # if dropout:
        #    layers.append(nn.Dropout(dropout))

        self.model = nn.Sequential(*layers)

    def forward(self, x, skip_input):
        x = self.model(x)
        x = torch.cat((x, skip_input), 1)
        return x


class GeneratorUNet(nn.Module):
    def __init__(self, in_channels=1, out_channels=1):
        super(GeneratorUNet, self).__init__()

        self.down1 = UNetDown(in_channels, 64, normalize=False)
        self.down2 = UNetDown(64, 128)
        self.down3 = UNetDown(128, 256)
        self.down4 = UNetDown(256, 512)  # , dropout=0.5)
        self.down5 = UNetDown(512, 512)  # , dropout=0.5)
        self.down6 = UNetDown(512, 512)  # , dropout=0.5)
        self.down7 = UNetDown(512, 512)  # , dropout=0.5)
        self.down8 = UNetDown(512, 512)  # , dropout=0.5)

        self.up1 = UNetUp(512 + 3, 512)  # , dropout=0.5)
        self.up2 = UNetUp(1024, 512)  # , dropout=0.5)
        self.up3 = UNetUp(1024, 512)  # , dropout=0.5)
        self.up4 = UNetUp(1024, 512)  # , dropout=0.5)
        self.up5 = UNetUp(1024, 256)
        self.up6 = UNetUp(512, 128)
        self.up7 = UNetUp(256, 64)

        self.final = nn.Sequential(
            nn.ConvTranspose2d(128, out_channels, 4, 2, 1),
            # nn.Upsample(scale_factor=2),
            # nn.ZeroPad2d((1, 0, 1, 0)),
            nn.Conv2d(out_channels, out_channels, 3, 1, 1),
            # nn.Tanh(),
            nn.Sigmoid(),
        )

    def forward(self, x, quality):
        # U-Net generator with skip connections from encoder to decoder

        d1 = self.down1(x)
        d2 = self.down2(d1)
        d3 = self.down3(d2)
        d4 = self.down4(d3)
        d5 = self.down5(d4)
        d6 = self.down6(d5)  # [16, 512, 4, 4]
        d7 = self.down7(d6)  # [16, 512, 2, 2]
        d8 = self.down8(d7)  # [16, 512, 1, 1]

        quality = torch.transpose(quality, 1, 2).unsqueeze(3)
        d8 = torch.cat((d8, quality), 1)  # [16, 515, 1, 1]

        u1 = self.up1(d8, d7)
        u2 = self.up2(u1, d6)

        u3 = self.up3(u2, d5)

        u4 = self.up4(u3, d4)
        u5 = self.up5(u4, d3)
        u6 = self.up6(u5, d2)
        u7 = self.up7(u6, d1)

        return self.final(u7)


##############################
#        Discriminator
##############################


class Discriminator(nn.Module):
    def __init__(self, in_channels=1):
        super(Discriminator, self).__init__()

        def discriminator_block(in_filters, out_filters, normalization=True):
            """Returns downsampling layers of each discriminator block"""
            layers = [nn.Conv2d(in_filters, out_filters, 4, stride=2, padding=1),
                      nn.BatchNorm2d(out_filters),
                      nn.LeakyReLU(0.2, inplace=True)]

            return layers

        self.model = nn.Sequential(
            *discriminator_block(in_channels * 2, 64, normalization=False),
            *discriminator_block(64, 128),
            *discriminator_block(128, 256),
            *discriminator_block(256, 512),
            nn.ZeroPad2d((1, 0, 1, 0)),
            nn.Conv2d(512, 1, 4, padding=1, bias=False)
        )

    def forward(self, condition, target):  # [16, 1, 256, 256], [16, 1, 256, 256]
        # Concatenate image and condition image by channels to produce input
        img_input = torch.cat((condition, target), 1)  # [16, 2, 256, 256]
        return self.model(img_input)
