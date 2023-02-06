from typing import Dict, List, Tuple, Iterable
from enum import Enum
from random import choice, randint, choices
import sys

import pygame
from pygame.locals import *

import data.engine as e


WINDOW_SIZE = (600,400)
DISPLAY_SIZE = (300,200)
# DISPLAY_SIZE = WINDOW_SIZE
ZOOM_X = WINDOW_SIZE[0]/DISPLAY_SIZE[0]
CHUNK_SIZE = 8 # length of chunk (in no. of tiles).

clock = pygame.time.Clock()

pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
pygame.mixer.set_num_channels(64)

pygame.display.set_caption('Pygame Platformer')

screen = pygame.display.set_mode(WINDOW_SIZE,0,32)
display = pygame.Surface(DISPLAY_SIZE) # used as the surface for rendering, which is scaled

moving_right = False
moving_left = False
vertical_momentum = 0
air_timer = 0

true_scroll = e.Vector(0,0)


grass_img = pygame.image.load('data/images/grass.png')
dirt_img = pygame.image.load('data/images/dirt.png')
plant_img = pygame.image.load('data/images/plant.png').convert()
plant_img.set_colorkey((255,255,255))


class TileType(Enum):
    NOTHING = None
    GRASS = grass_img
    DIRT = dirt_img
    PLANT = plant_img


class MoveKey(Enum):
    UP = K_SPACE
    RIGHT = K_f
    DOWN = K_d
    LEFT = K_s


class Tile:
    def __init__(self, x:int, y:int, tile_type:'TileType'):
        '''Element occupying one tile in the game map'''
        self.x = x
        self.y = y
        self.type = tile_type


class BackgroundObject:
    def __init__(self, parallax: float, rect: pygame.Rect):
        self.parallax = parallax
        self.rect = rect
        self.spawn_x = rect.x
        self.spawn_y = rect.y

    def move(self, delta_x: int, delta_y: int):
        # self.rect.move(delta_x, delta_y)
        self.rect.x += delta_x
        self.rect.y -= delta_y

    def parallax_move(self, delta_x, delta_y, from_spawn:bool=False):
        '''Move self considering parallax.
        * from_spawn makes the move relative to spawn position'''
        self.place_at(delta_x*self.parallax, delta_y*self.parallax, from_spawn)

    def place_at(self, x, y, from_spawn:bool=False)->None:
        '''Positions rect at new coordinates'''
        self.rect.x = self.spawn_x + x if from_spawn else x
        self.rect.y = self.spawn_y + y if from_spawn else y

    def is_viewable(self):
        view_rect = get_draw_rect(self.rect, self.parallax)
        return view_rect.x > -self.rect.width and view_rect.x < DISPLAY_SIZE[0]


class Backgrounds(list):
    def __init__(self, iterable:Iterable=None):
        for e in iterable:
            self.append(e)


def get_draw_rect(rect: pygame.Rect, parallax: int)->pygame.Rect:
    '''Returns the draw coordinates considering:
    * a parallax
    * the display size
    * the zoom levels (defined by the display to screen ratios of the x, y axis)'''
    adjusted_x = (player.x - scroll.x) - ((player.x-rect.x) * parallax)
    # adjusted_x = (rect.x - scroll.x) * parallax

    # adjusted_y = (rect.y - scroll.y) * parallax
    adjusted_y = (player.y - scroll.y) - ((player.y-rect.y) * parallax)
    adjusted_width = rect.width * parallax
    adjusted_height = rect.height * parallax
    parallaxed = [adjusted_x, adjusted_y, adjusted_width, adjusted_height]
    parallaxed = [int(value) for value in parallaxed]
    return pygame.Rect(parallaxed)


def generate_chunk(chunk_x:int,chunk_y:int)->List[Tile]:
    '''
    Generate all the tiles for a new chunk
    Tile instances of type empty are discarded.
    '''    
    tiles = []
    for row in range(CHUNK_SIZE):
        for column in range(CHUNK_SIZE):
            tile = Tile(x=chunk_x * CHUNK_SIZE + column,
                        y=chunk_y * CHUNK_SIZE + row,
                        tile_type = TileType.NOTHING)
            tile_type = TileType.NOTHING

            # create hole
            if tile.x >= 6 and tile.x <= 8:
                continue

            if tile.y > 10:
                tile_type = TileType.DIRT
                tile.type = TileType.DIRT
            elif tile.y == 10:
                tile_type = TileType.GRASS
                tile.type = TileType.GRASS
            elif tile.y == 9:
                if not randint(0,4):
                    tile_type = TileType.PLANT
                    tile.type = TileType.PLANT
            if tile_type != TileType.NOTHING:
                tiles.append(tile)
    return tiles


e.load_animations('data/images/entities/')

game_map:Dict[str,Tile] = {}

jump_sounds = [pygame.mixer.Sound('data/audio/jump.wav'), pygame.mixer.Sound('data/audio/jump2.wav')]
grass_sounds = [pygame.mixer.Sound('data/audio/grass_0.wav'),pygame.mixer.Sound('data/audio/grass_1.wav')]
grass_sounds[0].set_volume(0.2)
grass_sounds[1].set_volume(0.2)

pygame.mixer.music.load('data/audio/music.wav')
pygame.mixer.music.play(-1)

grass_sound_timer = 0

player = e.entity(0,100,5,13,'player')
grass_tiles:List[pygame.Rect] = []

# background tiles
BG_OBJ_WIDTH = 40
BG_OBJ_HEIGHT = 100
BG_OBJ_X =  0 - round(BG_OBJ_WIDTH/2)
BG_OBJ_Y = 150+16-BG_OBJ_HEIGHT
print(f'{BG_OBJ_X + randint(-DISPLAY_SIZE[0]/2, (DISPLAY_SIZE[0]-BG_OBJ_WIDTH)/2+BG_OBJ_WIDTH)/0.1=}')
background_objects = [
    BackgroundObject(parallax/100,          
                    pygame.Rect(BG_OBJ_X + round(randint(-DISPLAY_SIZE[0]/2, (DISPLAY_SIZE[0]-BG_OBJ_WIDTH)/2+BG_OBJ_WIDTH)*100/parallax),
                                 BG_OBJ_Y,
                                 BG_OBJ_WIDTH,
                                 BG_OBJ_HEIGHT
                                 )
                    ) for parallax in range(6, 101)]

####
# game loop
###########
while True:
    display.fill(color=(146,244,255)) # clear screen by filling it with blue

    # grass sound adjustment
    grass_sound_timer -= 1
    grass_sound_timer = max(grass_sound_timer, 0)

    # camera
    true_scroll.x += (player.x-true_scroll.x-DISPLAY_SIZE[0]/2)#/20
    true_scroll.y += (player.y-true_scroll.y-106)#/20
    scroll = true_scroll.copy()
    scroll.x = int(scroll.x)
    scroll.y = int(scroll.y)

    # draw background elements
    ## ground past the tiles
    pygame.draw.rect(display,
                     color=(160,150,14),
                     rect=pygame.Rect(0,
                                      player.y - scroll.y,
                                      DISPLAY_SIZE[0],DISPLAY_SIZE[1]))

    ## background structures
    for background_object in background_objects:
        if background_object.is_viewable():
            tint1 = round((1-(1 - background_object.parallax)) * 255)
            tint2 = round((1 - background_object.parallax) * 255)
            draw_rect = get_draw_rect(background_object.rect, background_object.parallax)
            pygame.draw.rect(display,(tint1,tint2,255),draw_rect)
    
    # generate and display tiles
    tile_rects = []
    grass_tiles = []
    for y in range(6):
        for x in range(7):
            target_x = x - 1 + int(round(scroll.x/(CHUNK_SIZE*16)))
            target_y = y - 1 + int(round(scroll.y/(CHUNK_SIZE*16)))
            chunk_position = str(target_x) + ';' + str(target_y)
            if chunk_position not in game_map:
                game_map[chunk_position] = generate_chunk(target_x, target_y)
            for tile in game_map[chunk_position]:
                display.blit(tile.type.value,(tile.x*16-scroll.x, tile.y*16-scroll.y))
                if tile.type in [TileType.GRASS, TileType.DIRT]:
                    tile_rects.append(pygame.Rect(tile.x*16,tile.y*16,16,16))
                if tile.type == TileType.PLANT:
                    grass_tiles.append(pygame.Rect(tile.x*16,tile.y*16,16,16))

    # player movement
    player_movement = e.Vector(x=0,y=0)
    if moving_right == True:
        player_movement.x += 2
    if moving_left == True:
        player_movement.x -= 2
    player_movement.y += vertical_momentum
    vertical_momentum += 0.2
    if vertical_momentum > 3:
        vertical_momentum = 3

    # player animations
    if player_movement.x == 0:
        player.set_action('idle')
    if player_movement.x > 0:
        player.set_flip(False)
        player.set_action('run')
    if player_movement.x < 0:
        player.set_flip(True)
        player.set_action('run')

    # player collisions
    collision_types = player.move(player_movement,tile_rects)
    if collision_types['bottom'] == True:
        # play grass sound
        if air_timer > 3 or player_movement.x != 0:
            if any((player.rect().colliderect(grass) for grass in grass_tiles)):
                if grass_sound_timer == 0:
                    grass_sound_timer = 30
                    choice(grass_sounds).play()
        air_timer = 0
        vertical_momentum = 0
    else:
        air_timer += 1

    # player visuals
    player.change_frame(1)
    player.display(display,scroll)

    # key inputs
    for event in pygame.event.get(): # event loop
        if event.type == QUIT:
            pygame.quit()
            sys.exit()
        if event.type == KEYDOWN:
            if event.key == K_w:
                pygame.mixer.music.fadeout(1000)
            if event.key == MoveKey.RIGHT.value:
                moving_right = True
            if event.key == MoveKey.LEFT.value:
                moving_left = True
            if event.key == MoveKey.UP.value:
                if air_timer < 600:
                    choice(jump_sounds).play()
                    vertical_momentum = -5
            if event.key == MoveKey.DOWN.value and vertical_momentum < 0:
                    vertical_momentum = 0
        if event.type == KEYUP:
            if event.key == MoveKey.RIGHT.value:
                moving_right = False
            if event.key == MoveKey.LEFT.value:
                moving_left = False
            if event.key == MoveKey.UP.value and vertical_momentum < 0:
                vertical_momentum = 0
        
    screen.blit(pygame.transform.scale(display,WINDOW_SIZE),(0,0))
    pygame.display.update()
    clock.tick(60)
