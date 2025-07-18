"""REST API控制器模块"""

from webob import Response
import json
try:
    from ryu.app.wsgi import ControllerBase, route
except ImportError:
    # 为了本地开发环境兼容性
    class ControllerBase:
        def __init__(self, req, link, data, **config):
            pass
    
    def route(name, path, methods=None):
        def decorator(func):
            return func
        return decorator


class APIController(ControllerBase):
    """REST API控制器"""
    
    def __init__(self, req, link, data, **config):
        super(APIController, self).__init__(req, link, data, **config)
        
        self.whitelistManager = data['whitelistManager']
        self.trafficMonitor = data['trafficMonitor']
    
    @staticmethod
    def createResponse(data=None, status=200, message=None):
        """创建标准响应"""
        response = {
            'status': status,
            'message': message or ('success' if status == 200 else 'error'),
            'data': data or {}
        }
        return Response(
            body=json.dumps(response),
            status=status,
            content_type='application/json'
        )
    
    def addToWhitelist(self, req, **kwargs):
        """添加MAC地址到白名单"""
        try:
            mac = req.json.get('mac')
            if not mac:
                return self.createResponse(status=400, message='MAC address is required')
            
            if self.whitelistManager.addToWhitelist(mac):
                return self.createResponse(message=f'MAC {mac} added to whitelist')
            else:
                return self.createResponse(status=409, message=f'MAC {mac} already in whitelist')
                
        except Exception as e:
            return self.createResponse(status=500, message=str(e))
    
    def removeFromWhitelist(self, req, **kwargs):
        """从白名单中移除MAC地址"""
        try:
            mac = req.json.get('mac')
            if not mac:
                return self.createResponse(status=400, message='MAC address is required')
            
            if self.whitelistManager.removeFromWhitelist(mac):
                return self.createResponse(message=f'MAC {mac} removed from whitelist')
            else:
                return self.createResponse(status=404, message=f'MAC {mac} not found in whitelist')
                
        except Exception as e:
            return self.createResponse(status=500, message=str(e))
    
    def getWhitelist(self, req, **kwargs):
        """获取当前白名单"""
        try:
            whitelist = self.whitelistManager.getWhitelist()
            return self.createResponse(data={'whitelist': whitelist})
        except Exception as e:
            return self.createResponse(status=500, message=str(e))
    
    def getTrafficStats(self, req, **kwargs):
        """获取流量统计"""
        try:
            mac = req.params.get('mac')
            stats = self.trafficMonitor.getTraffic(mac)
            return self.createResponse(data=stats)
        except Exception as e:
            return self.createResponse(status=500, message=str(e))
    
    def getTopUsers(self, req, **kwargs):
        """获取流量使用最多的用户"""
        try:
            limit = int(req.params.get('limit', 10))
            topUsers = self.trafficMonitor.getTopUsers(limit)
            return self.createResponse(data={'topUsers': topUsers})
        except Exception as e:
            return self.createResponse(status=500, message=str(e))


# 注册路由
try:
    from ryu.app.wsgi import route
    
    APIController.route = route
    
    # 注册路由
    APIController.route('api', '/addToWhitelist', methods=['POST'])(APIController.addToWhitelist)
    APIController.route('api', '/removeFromWhitelist', methods=['POST'])(APIController.removeFromWhitelist)
    APIController.route('api', '/whitelist', methods=['GET'])(APIController.getWhitelist)
    APIController.route('api', '/traffic', methods=['GET'])(APIController.getTrafficStats)
    APIController.route('api', '/topUsers', methods=['GET'])(APIController.getTopUsers)
except ImportError:
    # 如果ryu不可用，跳过路由注册
    pass
