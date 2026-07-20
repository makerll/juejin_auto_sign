    async def publish_order(self, robot_name: str, order: OrderMessage):
        """
        发布订单到机器人

        Args:
            robot_name: 机器人名称
            order: VDA5050订单消息
        """
        topic = f"{MANUFACTURER}/{robot_name}/order"
        payload = order.model_dump_json()

        try:
            await self.client.publish(topic, payload, qos=1)
            logger.info(f"Published order {order.orderId} to {robot_name}")
        except Exception as e:
            logger.error(f"Failed to publish order to {robot_name}: {e}")
            raise
