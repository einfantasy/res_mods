API_VERSION = 'API_v1.0'
MOD_NAME = 'ThreeDimentionalHydro'
LOGGER_NAME = '{}, ModsAPI'.format(MOD_NAME)


try:
    import constants, events, battle, utils, callbacks, dataHub
except:
    pass

import SpatialUI
from Math import Matrix
from math import pi


DEPTH_TEST_BITS = SpatialUI.DT_BIT_ENABLE | SpatialUI.DT_BIT_INSIDE_BOX
HALF_PI = pi / 2.0

class Colors(object):
    RED = 0xFFFF3300
    WHITE = 0xFFFFFFFF
    GREEN = 0xFf4ce8aa
    ORANGE = 0xFfFF9933
    NONE = 0


class DefaultAlphaFactors(object):
    MAX = 0.5
    ANIMATION_MIN_COEFF = 0.15
    ZERO = 0.0
    IDLE = 0.2


class HydroColors(object):
    ALLY = {
        constants.ConsumableStates.READY      : Colors.WHITE,
        constants.ConsumableStates.AT_WORK    : Colors.GREEN,
        constants.ConsumableStates.RELOAD     : Colors.ORANGE,
        constants.ConsumableStates.PREPARATION: Colors.ORANGE,
        constants.ConsumableStates.NO_AMMO    : Colors.NONE,
    }
    ENEMY = {
        constants.ConsumableStates.READY      : Colors.WHITE,
        constants.ConsumableStates.AT_WORK    : Colors.RED,
        constants.ConsumableStates.RELOAD     : Colors.ORANGE,
        constants.ConsumableStates.PREPARATION: Colors.ORANGE,
        constants.ConsumableStates.NO_AMMO    : Colors.NONE,
    }

CIRCLE_ALPHA_MAX        = 1.0
CIRCLE_ALPHA_MIN        = 0.15
CIRCLE_ALPHA_IDLE       = 0.7
CIRCLE_LINE_WIDTH       = 3
CIRCLE_BLINK_TIME       = 1.0
CIRCLE_BLINK_START_TIME = 7.0


class HydroAlphas(object):
    DEFAULT = {}
    ENEMY_IN_RANGE = {}


class HydroRangeOffset(object):
    METER_TO_BW = 1.0 / 30.0
    STEP_METER = 500.0
    STEP_BW = STEP_METER * METER_TO_BW
    DEFAULT_OFFSET_METER = 1000.0
    DEFAULT_OFFSET_BW = DEFAULT_OFFSET_METER * METER_TO_BW
    OFFSET_BW = 0


HYDRO_USERPREF_NUM_SECTION = 'chatBoxWidth'
HYDRO_USERPREF_CONFIGS = [
    {'prefKey': '3dHydroCircleOpacityReady', 'saveTo': HydroAlphas.DEFAULT, 'saveKey': constants.ConsumableStates.READY,  'default': DefaultAlphaFactors.IDLE, 'prefMultiplier': 0.1},
    {'prefKey': '3dHydroCircleOpacityReady', 'saveTo': HydroAlphas.DEFAULT, 'saveKey': constants.ConsumableStates.SELECTED,'default': DefaultAlphaFactors.IDLE, 'prefMultiplier': 0.1},
    {'prefKey': '3dHydroCircleOpacityActive','saveTo': HydroAlphas.DEFAULT, 'saveKey': constants.ConsumableStates.AT_WORK,'default': DefaultAlphaFactors.IDLE, 'prefMultiplier': 0.1},
    {'prefKey': '3dHydroCircleOpacityReload','saveTo': HydroAlphas.DEFAULT, 'saveKey': constants.ConsumableStates.RELOAD, 'default': DefaultAlphaFactors.IDLE, 'prefMultiplier': 0.1},
    {'prefKey': '3dHydroCircleOpacityReload','saveTo': HydroAlphas.DEFAULT, 'saveKey': constants.ConsumableStates.PREPARATION, 'default': DefaultAlphaFactors.IDLE, 'prefMultiplier': 0.1},
    {'prefKey': '3dHydroCircleOpacityNoAmmo','saveTo': HydroAlphas.DEFAULT, 'saveKey': constants.ConsumableStates.NO_AMMO, 'default': DefaultAlphaFactors.ZERO, 'prefMultiplier': 0.1},
    {'prefKey': '3dHydroCircleOpacityReadyWithEnemy', 'saveTo': HydroAlphas.ENEMY_IN_RANGE, 'saveKey': constants.ConsumableStates.READY,  'default': DefaultAlphaFactors.IDLE, 'prefMultiplier': 0.1},
    {'prefKey': '3dHydroCircleOpacityReadyWithEnemy', 'saveTo': HydroAlphas.ENEMY_IN_RANGE, 'saveKey': constants.ConsumableStates.SELECTED, 'default': DefaultAlphaFactors.IDLE, 'prefMultiplier': 0.1},
    {'prefKey': '3dHydroCircleOpacityActiveWithEnemy','saveTo': HydroAlphas.ENEMY_IN_RANGE, 'saveKey': constants.ConsumableStates.AT_WORK,'default': DefaultAlphaFactors.MAX, 'prefMultiplier': 0.1},
    {'prefKey': '3dHydroCircleOpacityReloadWithEnemy','saveTo': HydroAlphas.ENEMY_IN_RANGE, 'saveKey': constants.ConsumableStates.RELOAD, 'default': DefaultAlphaFactors.IDLE, 'prefMultiplier': 0.1},
    {'prefKey': '3dHydroCircleOpacityReloadWithEnemy','saveTo': HydroAlphas.ENEMY_IN_RANGE, 'saveKey': constants.ConsumableStates.PREPARATION, 'default': DefaultAlphaFactors.IDLE, 'prefMultiplier': 0.1},
    {'prefKey': '3dHydroCircleOpacityNoAmmoWithEnemy','saveTo': HydroAlphas.ENEMY_IN_RANGE, 'saveKey': constants.ConsumableStates.NO_AMMO, 'default': DefaultAlphaFactors.ZERO, 'prefMultiplier': 0.1},
    {'prefKey': '3dHydroCircleRangeOffset','saveTo': HydroRangeOffset, 'saveKey': 'OFFSET_BW', 'saveAsAttr': True, 'default': HydroRangeOffset.DEFAULT_OFFSET_BW, 'prefMultiplier': HydroRangeOffset.STEP_BW},
]
class UserPrefsManager(object):
    @classmethod
    def loadUserPrefs(cls, entity):
        userPrefsComp = entity[constants.UiComponents.userPrefs]
        userPrefsNum = userPrefsComp.userPrefs.get(HYDRO_USERPREF_NUM_SECTION, {})
        # chatBoxWidth does not exist until the relevent entry is written.
        # So it should at least return empty dict instead of None.
        # Returning Null leads to an error when the client is newly installed or the userpref is erased/reset.
        cls.__updatePrefs(userPrefsNum)
        userPrefsComp.evUserPrefsChanged.add(cls.onUserPrefsChanged)
        utils.logInfo(LOGGER_NAME, 'Loaded UserPrefs.')

    @classmethod
    def onUserPrefsChanged(cls, component):
        try:
            userPrefsNum = component.userPrefs.get(HYDRO_USERPREF_NUM_SECTION, {})
            cls.__updatePrefs(userPrefsNum)
        except:
            pass

    @classmethod
    def __updatePrefs(cls, userPrefsNum):
        for config in HYDRO_USERPREF_CONFIGS:
            prefKey = config['prefKey']
            prefMultiplier = config['prefMultiplier']
            saveObj = config['saveTo']
            saveKey = config['saveKey']
            default = config['default'] / prefMultiplier

            value = round(userPrefsNum.get(prefKey, default)) * prefMultiplier
            if config.get('saveAsAttr', False):
                setattr(saveObj, saveKey, value)
            else:
                saveObj[saveKey] = value


# Drawer
class ThreeDimentionalHydroDrawer(object):
    def __init__(self, vehicle):
        self.vehicle = vehicle
        self.currentBlinkTime = 0.0
        self.hydroDist = vehicle.getHydroAcousticSearchInfo().distShip
        # mesh
        self.hydroCircle = None
        self.colorTable = self.__getColorTable()
        # other
        self.updateTimer = None
        self.prevDrawTime = utils.getTimeFromGameStart()
        self.initMesh()
        self.startDrawing()
        utils.logInfo(LOGGER_NAME, 'Hydro Drawer started.')

    def initMesh(self):
        # circle contour
        hydroCircle = SpatialUI.EllipseContour(1, SpatialUI.LDR)
        hydroCircle.lineWidth = CIRCLE_LINE_WIDTH
        hydroCircle.color = Colors.NONE
        hydroCircle.visible = False
        hydroCircle.set((0.0, 0.0, 0.0), self.hydroDist*2, self.hydroDist*2)
        # params
        params = SpatialUI.Params()
        params.depthTestBits = DEPTH_TEST_BITS
        SpatialUI.setParams(hydroCircle, params)

        self.hydroCircle = hydroCircle

    def kill(self, *args):
        try:
            self.stopDrawing()
            self.hydroCircle = None
            self.vehicle = None
            self.colorTable = None
            self.prevDrawTime = None
            self.hydroDist = None
            utils.logInfo(LOGGER_NAME, 'Hydro Drawer killed.')
        except:
            pass

    def startDrawing(self):
        self.updateTimer = callbacks.perTick(self.draw)

    def stopDrawing(self):
        try:
            self.hydroCircle.visible = False
            callbacks.cancel(self.updateTimer)
            self.updateTimer = None
        except:
            pass

    def getTransform(self, position):
        m = Matrix()
        m.setPosRotateRPY(position, (0.0, HALF_PI, 0))
        return m
        
    def draw(self):
        vehicle = self.vehicle
        if vehicle is None or not vehicle.isAlive():
            # isAlive essentially checks the entity existence in the world.
            # vehicle will not be nullified when it is unloaded from the client, e.g. going out of rendering range.
            # in such a case, vehicle will return None for `getHydroAcousticSearchInfo`
            utils.logInfo(LOGGER_NAME, 'Ship does not exist, or is being unloaded from the world.')
            self.stopDrawing()
            return
        
        currentTime = utils.getTimeFromGameStart()
        dt = currentTime - self.prevDrawTime
        self.prevDrawTime = currentTime
        
        hydroInfo = vehicle.getHydroAcousticSearchInfo()
        hydroCircle = self.hydroCircle
        state = hydroInfo.state
        isVisible = self.getVisibility(state)
        hydroCircle.visible = isVisible

        if isVisible is False:
            return
        
        hydroCircle.color = self.colorTable[state]
        hydroCircle.alphaFactor = self.getAlpha(dt, state, hydroInfo.workTimeLeft)
        hydroCircleMatrix = self.getTransform(vehicle.getPosition())
        SpatialUI.setTransform(hydroCircle, hydroCircleMatrix)

    def getVisibility(self, state):
        if battle.cameraAltVision():
            return True
        if state == constants.ConsumableStates.AT_WORK:
            return True
        return False

    def getAlpha(self, dt, state, workTimeLeft):
        circleAlphas = HydroAlphas.ENEMY_IN_RANGE if self.hasEnemyInRange else HydroAlphas.DEFAULT
        baseAlpha = circleAlphas[state]
        if state == constants.ConsumableStates.AT_WORK and workTimeLeft <= CIRCLE_BLINK_START_TIME:
            blinkCoef = self.currentBlinkTime / CIRCLE_BLINK_TIME
            if self.currentBlinkTime == CIRCLE_BLINK_TIME:
                self.currentBlinkTime = 0.0
            self.currentBlinkTime = min(self.currentBlinkTime + dt, CIRCLE_BLINK_TIME)
            return lerp(baseAlpha, baseAlpha * DefaultAlphaFactors.ANIMATION_MIN_COEFF, blinkCoef)
        else:
            self.currentBlinkTime = 0.0
            return baseAlpha

    def __getColorTable(self):
        playerInfo = battle.getSelfPlayer()
        playerTeamId = playerInfo.teamId
        if playerInfo.isObserver: #Observer: 0=ally, 1=enemy
            playerTeamId = 0
        if playerTeamId == self.vehicle.teamId: #ally
            return HydroColors.ALLY
        else:
            return HydroColors.ENEMY
        
    @property
    def hasEnemyInRange(self):
        ownVehicle = self.vehicle
        radius = self.hydroDist + HydroRangeOffset.OFFSET_BW
        for ship in battle.getAllShips():
            if ship.teamId == ownVehicle.teamId:
                pass
            elif not ship.isAlive():
                pass
            elif ship.uiId == ownVehicle.uiId:
                pass
            elif not battle.isInsideCircle(ownVehicle, radius, ship):
                pass
            else:
                return True

        return False
    
    @property
    def isDrawing(self):
        return self.updateTimer is None


def lerp(start, end, coef):
    return start + coef * (end - start)


class HydroDrawersManager(object):
    def __init__(self):
        self.drawers = {}
        self.updateTimer = None
        pass

    def init(self):
        self.updateTimer = callbacks.perTick(self.update)

    def update(self):
        # Alternativily
        # drawers = {}
        # for ship in battle.getAllShips():
        #     uiId = ship.uiId
        #     isAlive = ship.isAlive()
        #     hydroInfo = ship.getHydroAcousticSearchInfo()
        #     if hydroInfo:
        #         # New ship spotted
        #         if uiId not in self.drawers and isAlive:
        #             drawer[uiId] = ThreeDimentionalHydroDrawer(ship)
        #         # Ship already exists
        #         elif uiId in self.drawers:
        #             drawer = self.drawers.pop(uiId)
        #             if isAlive:
        #                 drawers[uiId] = drawer
        #             else:
        #                 drawer.kill()
        
        # for drawer in self.drawers.values():
        #     drawer.kill()
        
        # self.drawers = drawers



        visibleShipIds = set()
        for ship in battle.getAllShips():
            uiId = ship.uiId
            isAlive = ship.isAlive()
            hydroInfo = ship.getHydroAcousticSearchInfo()
            if hydroInfo:
                visibleShipIds.add(uiId)
                # New ship spotted
                # Check if "dead" ships are spotted as new
                if uiId not in self.drawers and isAlive:
                    self.drawers[uiId] = ThreeDimentionalHydroDrawer(ship)
                # Dead Ship
                elif uiId in self.drawers and not isAlive:
                    drawer = self.drawers.pop(uiId)
                    drawer.kill()
        # Ships gone dark
        for id in self.drawers.keys():
            if id in visibleShipIds:
                continue
            drawer = self.drawers.pop(id)
            drawer.kill()

    def kill(self, *args):
        for drawer in self.drawers.values():
            drawer.kill()
        self.drawers.clear()
        callbacks.cancel(self.updateTimer)
        self.updateTimer = None


userPrefsEntity = dataHub.getSingleEntity('userPrefs')
UserPrefsManager.loadUserPrefs(userPrefsEntity)

_gHydroDrawersManager = HydroDrawersManager()
events.onBattleShown(_gHydroDrawersManager.init)
events.onBattleQuit(_gHydroDrawersManager.kill)
utils.logInfo(LOGGER_NAME, 'Init.')
