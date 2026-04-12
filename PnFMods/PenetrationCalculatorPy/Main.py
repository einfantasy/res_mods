API_VERSION = 'API_v1.0'
MOD_NAME = 'PenetrationCalculator'
LOGGER_NAME = 'ModsAPI, {}'.format(MOD_NAME)

try:
    import events, ui, callbacks, utils, constants, battle
except:
    pass

from math import cos, radians, degrees, floor

INF = float('inf')
INVALID_VALUE = -1
COMPONENT_ID = 'modPenetrationCalculator'

AP_SKIP_DATA = {
    4075209424: [
        {
            'alwaysRicochetCoef': 1.0,
            'bombKruppMultiplier': 1.0,
            'detonatorCoef': 1.0,
            'detonatorThresholdCoef': 1.0,
            'ricochetCoef': 1.0,
        },
        {
            'alwaysRicochetCoef': 1.0,
            'bombKruppMultiplier': 0.45,
            'detonatorCoef': 1.0,
            'detonatorThresholdCoef': 0.2,
            'ricochetCoef': 1.0,
        },
    ],
}


class PenetrationCalculator(object):
    def __init__(self):
        self.ammo = None
        self.updateTimer = None
        self.uiID = None
        self.isSquadronMode = False
        self.modifiers = None
        self.hoopRanging = None
        self._addEvents()

    def _addEvents(self):
        #events
        events.onArtilleryAmmoChanged(self.onAmmoChanged)
        events.onArtilleryFireModeChanged(self.onBurstModeChanged)
        events.onWeaponTypeChanged(self.onWeaponChanged)
        events.onSquadronActivated(self.onSquadronActivated)
        events.onSquadronDeactivated(self.onSquadronDeactivated)

    def _createDatahubComponent(self):
        if self.uiID:
            ui.deleteUiElement(self.uiID)
        self.uiID = ui.createUiElement()
        ui.addDataComponentWithId(self.uiID, COMPONENT_ID, {'penetration': INVALID_VALUE})

    def _removeDatahubComponent(self):
        ui.deleteUiElement(self.uiID)
        self.uiID = None

    def _startVary(self):
        if self.updateTimer:
            callbacks.cancel(self.updateTimer)
        self.updateTimer = callbacks.perTick(self.update)

    def _stopVary(self):
        callbacks.cancel(self.updateTimer)
        self.updateTimer = None

    def start(self, *args): 
        self.modifiers = battle.getAmmoModifiers()
        self._startVary()
        self._createDatahubComponent()
        utils.logInfo(LOGGER_NAME, 'Started update')

    def stop(self, *args):
        try:
            self._stopVary()
            self._removeDatahubComponent()
            self.isSquadronMode = False
            self.ammo = None
            self.modifiers = None
            self.hoopRanging = None
            utils.logInfo(LOGGER_NAME, 'Stopped update')
        except:
            #utils.logInfo(LOGGER_NAME, 'Error while trying to stop update')
            pass

    def _calcPenetration(self, ammo, impactSpeed):
        if ammo.ammoType == 'HE':
            return self.__calcHEPenetration(ammo)
        elif ammo.ammoType == 'CS':
            return int(ammo.alphaPiercingCS)
        elif ammo.ammoType == 'AP':
            return self.__calcAPPenetration(ammo, impactSpeed)
        # Other Ammunitions
        return INVALID_VALUE

    def __calcAPPenetration(self, ammo, impactSpeed):
        krupp = battle.getBulletKrupp(ammo, self.modifiers)
        raw = krupp * (ammo.bulletMass * impactSpeed * impactSpeed) ** 0.69 * ammo.bulletDiametr ** (-1.07) * 0.0000001
        if self.isSquadronMode:
            return raw
        return raw * cos(self.__calcImpactAngle(ammo))

    def __calcHEPenetration(self, ammo):
        penCoeff = 1.0
        if ammo.typeinfo.species == constants.ProjectileTypes.ARTILLERY:
            penCoeff = self.modifiers.GMPenetrationCoeffHE
        return int(ammo.alphaPiercingHE * penCoeff)

    def update(self):
        self.hoopRanging = battle.getSelfHoopRanging()
        if (not self.isSquadronMode and not self.hoopRanging.isReady) or self.ammo is None:
            ui.updateUiElementData(self.uiID, {'penetration': INVALID_VALUE})
            return
        ui.updateUiElementData(self.uiID, self.getPenetratonData())

    def getPenetratonData(self):
        ammo = self.ammo
        isAP = ammo.ammoType =='AP'
        isRicochetable = ammo.ammoType == 'CS' or isAP
        impactAgnle = self.hoopRanging.pitch
        impactSpeed = self._calcImpactSpeed(ammo)
        penetration = self._calcPenetration(ammo, impactSpeed)
        return dict(
            penetration         = penetration,
            startRicochet       = ammo.bulletRicochetAt if isRicochetable else INVALID_VALUE,
            alwaysRicochet      = ammo.bulletAlwaysRicochetAt if isRicochetable else INVALID_VALUE,
            detonatorDelay      = ammo.bulletDetonator if isAP else INVALID_VALUE,
            detonatorThreshold  = ammo.bulletDetonatorThreshold if isAP else INVALID_VALUE,
            detonatorLength     = impactSpeed * ammo.bulletDetonator if isAP else INVALID_VALUE,
            overmatch           = self._calcOvermatch(ammo) if isRicochetable else INVALID_VALUE,
            impactAngle         = degrees(impactAgnle) if not self.isSquadronMode else INVALID_VALUE,
            apSkipData          = self._calcAdditionalAPSkipData(ammo, penetration),
        )
    
    def _calcOvermatch(self, ammo):
        return floor(ammo.bulletDiametr * 1000 / 14.3)
    
    def __calcImpactAngle(self, ammo):
        normalizeAngle = radians(ammo.bulletCapNormalizeMaxAngle)
        trajAngle = abs(self.hoopRanging.pitch)
        return max(0, trajAngle - normalizeAngle)

    def _calcImpactSpeed(self, ammo):
        if self.isSquadronMode:
            return ammo.bulletSpeed if ammo.ammoType =='AP' else INVALID_VALUE
        
        hoopRanging = self.hoopRanging
        gunPos = hoopRanging.gunPos
        gunDir = hoopRanging.gunDir
        if gunPos.y >= 0.001:
            impactSpeed = battle.getAmmoImpactSpeed(ammo, gunPos, gunDir)
            if impactSpeed is not None:
                return impactSpeed
        return INVALID_VALUE
    
    def _calcAdditionalAPSkipData(self, ammo, pen):
        """
        None | dict
        """
        modifiers = AP_SKIP_DATA.get(ammo.id, None)
        if not modifiers:
            return None
        
        data = dict(
            penetrations = [ pen * mod['bombKruppMultiplier'] for mod in modifiers ],
            # detonatorDelays = [ ammo.bulletDetonator * mod['detonatorCoef'] for mod in modifiers],
            detonatorThresholds = [ ammo.bulletDetonatorThreshold * mod['detonatorThresholdCoef'] for mod in modifiers],
            # startRicochets = [ ammo.bulletRicochetAt * mod['ricochetCoef'] for mod in modifiers],
            # alwaysRicochets = [ ammo.bulletAlwaysRicochetAt * mod['alwaysRicochetCoef'] for mod in modifiers],
        )

        return data

    def onAmmoChanged(self, ammoId):
        if self.ammo is None or self.ammo.id != ammoId:
            self.ammo = battle.getAmmoParams(ammoId)

    def onWeaponChanged(self, weaponType):
        selectedAmmoId = INVALID_VALUE
        if weaponType == constants.WeaponType.ARTILLERY:
            selectedAmmoId = battle.getSelectedAmmoId(weaponType)
        self.onAmmoChanged(selectedAmmoId)

    def onSquadronActivated(self, bombParamsId):
        self.isSquadronMode = True
        self.onAmmoChanged(bombParamsId)

    def onSquadronDeactivated(self, *args):
        self.isSquadronMode = False
        self.onAmmoChanged(INVALID_VALUE)

    def onBurstModeChanged(self, *args):
        self.modifiers = battle.getAmmoModifiers()
        # Assuming the burst is not available outside of artillery
        selectedAmmoId = battle.getSelectedAmmoId(constants.WeaponType.ARTILLERY)
        # e.g. Victoria: burst fire may change the shells
        self.onAmmoChanged(selectedAmmoId)


_gPenCalculator = PenetrationCalculator()
events.onBattleShown(_gPenCalculator.start)
events.onBattleQuit(_gPenCalculator.stop)

utils.logInfo(LOGGER_NAME, 'Created an instance')