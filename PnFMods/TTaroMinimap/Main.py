API_VERSION = 'API_v1.0'
MOD_NAME = 'TTaroMinimap'

try:
    import events, ui, utils, dataHub, constants, battle
except:
    pass

from math import radians, degrees
from EntityController import EntityController


CC = constants.UiComponents
ShipTypes = constants.ShipTypes
KM_TO_BW = 1000.0 / 30.0


def logInfo(*args):
    data = [str(i) for i in args]
    utils.logInfo( '[{}] {}'.format(MOD_NAME, ', '.join(data)) )


class ShipConsumableChecker(object):
    """
    Checks the ship consumables in a match
    """

    COMPONENT_KEY = 'modTTaroMinimapConsumableRanges'

    TITLE_TO_INFO = {
        'RLSSearch'         : {'type': 'radar',             'attr': 'distShip'},
        'SonarSearch'       : {'type': 'hydro',             'attr': 'distShip'},
        'SubmarineLocator'  : {'type': 'subRadar',          'attr': 'acousticWaveMaxDist_submarine_detection'},
        #'Hydrophone'        : {'type': 'hydrophone',        'attr': 'hydrophoneWaveRadius'},
    }

    def __init__(self):
        self.entityController = EntityController(ShipConsumableChecker.COMPONENT_KEY)
        events.onBattleShown(self.__onBattleStart)
        events.onBattleQuit(self.__onBattleEnd)

    def __onBattleStart(self, *args):
        self.entityController.createEntity()
        data = self._getAllConsumablesData()
        self.entityController.updateEntity(data)

        logInfo('Ship consumables have been updated.')

    def __onBattleEnd(self, *args):
        self.entityController.removeEntity()

    def _getAllConsumablesData(self):
        consumablesData = {}
        for entity in dataHub.getEntityCollections('shipBattleInfo'):
            ship = entity[CC.shipBattleInfo]
            data = self._getConsumablesDataByShip(ship)
            if data is not None:
                consumablesData[ship.playerId] = data

        return consumablesData
    
    def _getConsumablesDataByShip(self, ship):
        data = {}
        allConsumables = ship.mainConsumables + [cons for consList in ship.altConsumables for cons in consList]
        for cons in allConsumables:
            consInfo = self.__getConsumableInfo(cons)
            if consInfo is None:
                continue
            consType = consInfo['type']
            data[consType] = self.__getConsumableRanges(cons, consInfo)

        if len(data) > 0:
            return data
        return None

    def __getConsumableInfo(self, consumable):
        consName = consumable.title
        for ident, consInfo in ShipConsumableChecker.TITLE_TO_INFO.iteritems():
            if ident.upper() in consName:
                return consInfo
        return None

    def __getConsumableRanges(self, consumable, consInfo):
        paramName = consInfo['attr']
        for attr in consumable.activeAttributes.neutral:
            if attr.paramName == paramName:
                bw = attr.numericValue * KM_TO_BW
                data = {'world': attr.numericValue, 'map': ui.getLengthOnMiniMap(bw)}
                return  data
            
consChecker = ShipConsumableChecker()



RPF_SECTOR_WIDTH_DEG = 360.0 / 16.0
RPF_SECTOR_WIDTH_RAD = radians(RPF_SECTOR_WIDTH_DEG)

RPF_SECTOR_HALF_WIDTH_DEG = RPF_SECTOR_WIDTH_DEG / 2.0
RPF_SECTOR_HALF_WIDTH_RAD = radians(RPF_SECTOR_HALF_WIDTH_DEG)

INVALID_DIRECTION = -1
RPF_MESSAGE_TO_DIRECTION = {
	'RPF: N~NNE':  1,
	'RPF: NNE~NE': 2,
	'RPF: NE~ENE': 3,
	'RPF: ENE~E':  4,
	'RPF: E~ESE':  5,
	'RPF: ESE~SE': 6,
	'RPF: SE~SSE': 7,
	'RPF: SSE~S':  8,
	'RPF: S~SSW':  9,
	'RPF: SSW~SW': 10,
	'RPF: SW~WSW': 11,
	'RPF: WSW~W':  12,
	'RPF: W~WNW':  13,
	'RPF: WNW~NW': 14,
	'RPF: NW~NNW': 15,
	'RPF: NNW~N':  16,
    'RPF: None':   INVALID_DIRECTION,
}


class RadioLocation(object):
    COMPONENT_KEY = 'modTTaroMinimapRadioLocation'

    def __init__(self):
        events.onBattleShown(self.__onBattleStart)
        events.onBattleQuit(self.__onBattleEnd)
        self.entityController = EntityController(RadioLocation.COMPONENT_KEY)
        self._selfPlayerId = 0
        self._rpfDirections = {}
        self._chatComponent = None
        self._rpfComponent = None

    def __onBattleStart(self, *args):
        self._rpfDirections.clear()
        self._selfPlayerId = battle.getSelfPlayerInfo().id
        chatEntity = dataHub.getSingleEntity('battleChatAndLog')
        if chatEntity:
            self.entityController.createEntity()

            chat = chatEntity[CC.battleChatAndLog]
            chat.evMessageReceived.add(self.__onChatReceived)
            self._chatComponent = chat

        rpfEntity = dataHub.getSingleEntity('nearestEnemyIndication')
        if rpfEntity:
            rpf = rpfEntity[CC.nearestEnemyIndication]
            rpf.evYawToNearestEnemyChanged.add(self.__onYawToNearestEnemyChanged)
            rpf.evShowNearestEnemyChanged.add(self.__onShowNearestEnemyChanged)
            self._rpfComponent = rpf
        
        logInfo('Initialized RPF controller')

    def __onBattleEnd(self, *args):
        if self._chatComponent:
            try:
                self._chatComponent.evMessageReceived.remove(self.__onChatReceived)
            except:
                logInfo('Error while trying to remove the event from chat')
            self._chatComponent = None

        if self._rpfComponent:
            rpf = self._rpfComponent
            try:
                rpf.evYawToNearestEnemyChanged.remove(self.__onYawToNearestEnemyChanged)
                rpf.evShowNearestEnemyChanged.remove(self.__onShowNearestEnemyChanged)
            except:
                logInfo('Error while trying to remove the event from RPF')

        self._rpfDirections.clear()
        self.entityController.removeEntity()
        self._selfPlayerId = 0

        logInfo('Cleared RPF controller')

    def __onYawToNearestEnemyChanged(self, component):
        rpfDirRad = component.yawToNearestEnemy - RPF_SECTOR_HALF_WIDTH_RAD

        self._rpfDirections[self._selfPlayerId] = degrees(rpfDirRad)
        self.entityController.updateEntity(self._rpfDirections)

    def __onShowNearestEnemyChanged(self, component):
        if component.showNearestEnemy:
            self.__onYawToNearestEnemyChanged(component)
        else:
            self.__updateDataByDirIndex(self._selfPlayerId, INVALID_DIRECTION)

    def __updateDataByDirIndex(self, playerId, rpfDirIndex):
        if rpfDirIndex != INVALID_DIRECTION:
            rpfDirRad = RPF_SECTOR_WIDTH_RAD * (rpfDirIndex - 1)
            self._rpfDirections[playerId] = degrees(rpfDirRad)
        else:
            self._rpfDirections[playerId] = INVALID_DIRECTION
        self.entityController.updateEntity(self._rpfDirections)

    def __onChatReceived(self, component):
        entity = dataHub.getEntityCollections('battleChatAndLogMessage')[-1]
        comp = entity[CC.battleChatAndLogMessage]
        senderId = comp.playerId
        if senderId == self._selfPlayerId:
            return
        # enemies may type chat directly
        # but the sector element isn't initialized for enemies in Unbound anyway
        rpfDirIndex = self._getDirectionIndex(comp.message)
        if rpfDirIndex is not None:
            self.__updateDataByDirIndex(senderId, rpfDirIndex)

    def _getDirectionIndex(self, message):
        # None if no signature is contained
        return RPF_MESSAGE_TO_DIRECTION.get(message, None)


gRadioLocation = RadioLocation()